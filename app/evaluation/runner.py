"""Run the question set against the real services and score each question.

Retrieval is always measured (no Gemini). The model answer is added only when a RagService
is passed. Services are injected, so tests use fakes and never call Gemini (I12).
"""

import time
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from app.core.errors import ExternalServiceError
from app.evaluation.metrics import (
    AnswerRecord,
    CitedRef,
    QuestionResult,
    RetrievedRef,
    is_expected_ref,
    satisfied_rank,
    sources_satisfied,
)
from app.evaluation.questions import EvalQuestion
from app.services.retrieval import DEFAULT_TOP_K, MAX_TOP_K

if TYPE_CHECKING:
    from app.services.rag import RagService
    from app.services.retrieval import RetrievalService

# One search per question returns the top 20, so every hit@k comes from the same list.
SEARCH_K = MAX_TOP_K
# Retrieved chunks kept in the result file (the largest cut-off in HIT_KS).
RECORDED_CHUNKS = 10
# Characters of each retrieved chunk kept in the result file, so a reader can see what was shown.
EXCERPT_CHARS = 300
# Free tier of gemini-3.5-flash-lite: 15 requests per minute (docs/provider_limits.md).
# One call every 5 s is 12 per minute, leaving room for other calls on the same project.
MIN_SECONDS_BETWEEN_CALLS = 5.0
# Stop after this many failed Gemini calls in a row: quota or an outage, not one bad question.
MAX_CONSECUTIVE_ERRORS = 3


class Pacer:
    """Keeps at least `min_interval` seconds between the starts of two calls."""

    def __init__(
        self,
        min_interval: float = MIN_SECONDS_BETWEEN_CALLS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last_start: float | None = None

    def wait(self) -> None:
        if self._last_start is not None:
            remaining = self._last_start + self._min_interval - self._clock()
            if remaining > 0:
                self._sleep(remaining)
        self._last_start = self._clock()


def evaluate_question(
    question: EvalQuestion,
    retrieval: "RetrievalService",
    rag: "RagService | None",
    pacer: Pacer,
    top_k: int = DEFAULT_TOP_K,
) -> QuestionResult:
    chunks = retrieval.search(question.question, SEARCH_K)
    rank = satisfied_rank(question, chunks) if question.expected_found else None
    retrieved = tuple(
        RetrievedRef(
            filename=chunk.filename,
            page_numbers=tuple(chunk.page_numbers),
            heading=chunk.heading,
            similarity=round(chunk.similarity, 4),
            matches_expected=is_expected_ref(question, chunk),
            excerpt=" ".join(chunk.text.split())[:EXCERPT_CHARS],
        )
        for chunk in chunks[:RECORDED_CHUNKS]
    )

    answer: AnswerRecord | None = None
    error: str | None = None
    if rag is not None:
        pacer.wait()
        try:
            reply = rag.ask(question.question, top_k=top_k)
        except ExternalServiceError as exc:
            # The message is generic by design (D-30); details are in the server log.
            error = f"{type(exc).__name__}: {exc}"
        else:
            answer = AnswerRecord(
                found=reply.found,
                text=reply.answer,
                citations=tuple(
                    CitedRef(
                        filename=citation.filename,
                        page_numbers=tuple(citation.page_numbers),
                        heading=citation.heading,
                        matches_expected=is_expected_ref(question, citation),
                    )
                    for citation in reply.citations
                ),
                sources_satisfied=sources_satisfied(question, reply.citations),
            )

    return QuestionResult(
        id=question.id,
        kind=question.kind,
        language=question.language,
        expected_found=question.expected_found,
        top_similarity=round(chunks[0].similarity, 4) if chunks else None,
        satisfied_rank=rank,
        retrieved=retrieved,
        answer=answer,
        error=error,
    )


def run_evaluation(
    questions: Sequence[EvalQuestion],
    retrieval: "RetrievalService",
    rag: "RagService | None",
    on_result: Callable[[QuestionResult], None],
    pacer: Pacer | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> bool:
    """Evaluate every question in order, reporting each result as soon as it exists.

    Returns True when all questions ran, False when it stopped early after repeated
    Gemini failures. Other errors (a bug, the database) are not caught: they stop the run
    loudly, and everything reported so far is already saved by the caller.
    """
    pacer = pacer or Pacer()
    failures_in_a_row = 0
    for question in questions:
        result = evaluate_question(question, retrieval, rag, pacer, top_k)
        on_result(result)
        failures_in_a_row = failures_in_a_row + 1 if result.error else 0
        if failures_in_a_row >= MAX_CONSECUTIVE_ERRORS:
            return False
    return True
