"""Scoring for the evaluation: pure functions and result records.

No database, no model, no network. A "ref" is anything with a file name and page numbers:
a retrieved chunk or a citation.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import mean
from typing import Any, Protocol

from app.evaluation.questions import EvalQuestion, ExpectedSource

# Retrieval is reported at these cut-offs (the answer cut-off is added by summarize).
HIT_KS = (1, 3, 5, 10)


class PageRef(Protocol):
    @property
    def filename(self) -> str: ...

    @property
    def page_numbers(self) -> Sequence[int]: ...


@dataclass(frozen=True)
class RetrievedRef:
    """A retrieved chunk: where it is, how close it was, and the start of its text."""

    filename: str
    page_numbers: tuple[int, ...]
    heading: str | None
    similarity: float
    matches_expected: bool
    # The first characters of the chunk text, on one line, so a reader can see what was shown.
    excerpt: str = ""


@dataclass(frozen=True)
class CitedRef:
    filename: str
    page_numbers: tuple[int, ...]
    heading: str | None
    matches_expected: bool


@dataclass(frozen=True)
class AnswerRecord:
    found: bool
    text: str
    citations: tuple[CitedRef, ...]
    sources_satisfied: bool


@dataclass(frozen=True)
class QuestionResult:
    id: str
    kind: str
    language: str
    expected_found: bool
    top_similarity: float | None
    # Smallest k whose top-k chunks satisfy the expected sources; None if never (or if
    # the question has no expected sources).
    satisfied_rank: int | None
    retrieved: tuple[RetrievedRef, ...]
    answer: AnswerRecord | None = None
    error: str | None = None


def source_matches(source: ExpectedSource, ref: PageRef) -> bool:
    """Same file and at least one shared page."""
    return ref.filename == source.file and bool(set(ref.page_numbers) & set(source.pages))


def is_expected_ref(question: EvalQuestion, ref: PageRef) -> bool:
    return any(source_matches(source, ref) for source in question.expected_sources)


def sources_satisfied(question: EvalQuestion, refs: Iterable[PageRef]) -> bool:
    """'any': one expected source is covered. 'all': every expected source is covered."""
    refs = list(refs)
    if not question.expected_sources:
        return False
    covered = [
        any(source_matches(source, ref) for ref in refs) for source in question.expected_sources
    ]
    return all(covered) if question.sources_match == "all" else any(covered)


def satisfied_rank(question: EvalQuestion, refs: Sequence[PageRef]) -> int | None:
    """The smallest k for which the first k refs satisfy the question's sources."""
    for k in range(1, len(refs) + 1):
        if sources_satisfied(question, refs[:k]):
            return k
    return None


def _rate(count: int, total: int) -> float | None:
    return round(count / total, 3) if total else None


def _count(count: int, total: int) -> dict[str, Any]:
    return {"count": count, "total": total, "rate": _rate(count, total)}


def _stats(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "min": round(min(values), 4),
        "mean": round(mean(values), 4),
        "max": round(max(values), 4),
    }


def summarize(results: Sequence[QuestionResult], answer_k: int) -> dict[str, Any]:
    """All headline numbers of a run. `answer_k` is the top_k the system answers with."""
    answerable = [r for r in results if r.expected_found]
    refusal = [r for r in results if not r.expected_found]
    cutoffs = sorted(set(HIT_KS) | {answer_k})

    def hit(result: QuestionResult, k: int) -> bool:
        return result.satisfied_rank is not None and result.satisfied_rank <= k

    by_kind: dict[str, dict[str, Any]] = {}
    for kind in sorted({r.kind for r in answerable}):
        rows = [r for r in answerable if r.kind == kind]
        by_kind[kind] = _count(sum(hit(r, answer_k) for r in rows), len(rows))

    top_answerable = [r.top_similarity for r in answerable if r.top_similarity is not None]
    top_refusal = [r.top_similarity for r in refusal if r.top_similarity is not None]

    retrieval = {
        "answerable_questions": len(answerable),
        "hit_at": {
            str(k): _count(sum(hit(r, k) for r in answerable), len(answerable)) for k in cutoffs
        },
        "mrr": (
            round(mean(1 / r.satisfied_rank if r.satisfied_rank else 0.0 for r in answerable), 3)
            if answerable
            else None
        ),
        "answer_k": answer_k,
        "hit_at_answer_k_by_kind": by_kind,
        "missed_at_answer_k": [r.id for r in answerable if not hit(r, answer_k)],
    }
    similarity = {
        "answerable": _stats(top_answerable),
        "refusal": _stats(top_refusal),
        "refusal_by_question": {r.id: r.top_similarity for r in refusal},
        # A threshold on the top similarity could refuse correctly only if every refusal
        # question scores below every answerable one.
        "threshold_would_separate": (
            max(top_refusal) < min(top_answerable) if top_answerable and top_refusal else None
        ),
    }

    return {
        "questions_run": len(results),
        "answerable": len(answerable),
        "to_refuse": len(refusal),
        "errors": [r.id for r in results if r.error],
        "retrieval": retrieval,
        "similarity": similarity,
        "generation": _summarize_generation(results),
    }


def _summarize_generation(results: Sequence[QuestionResult]) -> dict[str, Any] | None:
    pairs = [(r, r.answer) for r in results if r.answer is not None]
    if not pairs:
        return None

    answerable = [(r, a) for r, a in pairs if r.expected_found]
    refusal = [(r, a) for r, a in pairs if not r.expected_found]
    answered = [(r, a) for r, a in answerable if a.found]

    precisions = [
        sum(c.matches_expected for c in a.citations) / len(a.citations)
        for _, a in answered
        if a.citations
    ]
    padded = sum(1 for _, a in answered if any(not c.matches_expected for c in a.citations))

    return {
        "questions_with_model_answer": len(pairs),
        "answered_when_answerable": _count(len(answered), len(answerable)),
        "refused_when_unanswerable": _count(
            sum(1 for _, a in refusal if not a.found), len(refusal)
        ),
        "wrongly_refused": [r.id for r, a in answerable if not a.found],
        "wrongly_answered": [r.id for r, a in refusal if a.found],
        "citations": {
            "answers_checked": len(answered),
            "sources_satisfied": _count(
                sum(a.sources_satisfied for _, a in answered), len(answered)
            ),
            "with_padding": _count(padded, len(answered)),
            "mean_precision": round(mean(precisions), 3) if precisions else None,
            "mean_citations": (
                round(mean(len(a.citations) for _, a in answered), 2) if answered else None
            ),
        },
    }
