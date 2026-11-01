"""RAG: retrieve chunks, ask Gemini, and turn its answer into checked citations."""

import logging
import uuid
from dataclasses import dataclass

from app.services.llm import LlmService
from app.services.rag_prompt import SYSTEM_INSTRUCTION, RagReply, build_prompt
from app.services.retrieval import DEFAULT_TOP_K, RetrievalService, RetrievedChunk

logger = logging.getLogger(__name__)

# Fixed messages, used when no model text can be trusted or no model call is made.
NO_DOCUMENTS_MESSAGE = "There are no documents available to answer this question."
UNSUPPORTED_MESSAGE = "I could not find a supported answer in the documents."


@dataclass(frozen=True)
class Citation:
    """A source the answer is based on. Every field comes from the stored chunk."""

    document_id: uuid.UUID
    filename: str
    page_numbers: list[int]
    heading: str | None
    text: str


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    found: bool
    citations: list[Citation]


class RagService:
    """Answer a question from the documents, with citations the code has checked."""

    def __init__(self, retrieval: RetrievalService, llm: LlmService) -> None:
        self._retrieval = retrieval
        self._llm = llm

    def ask(self, question: str, top_k: int = DEFAULT_TOP_K) -> RagAnswer:
        # Invalid input raises ValidationFailedError here, before anything else happens.
        chunks = self._retrieval.search(question, top_k)
        if not chunks:
            logger.info("RAG: no chunks retrieved; Gemini was not called")
            return RagAnswer(answer=NO_DOCUMENTS_MESSAGE, found=False, citations=[])

        prompt = build_prompt(question, chunks)
        reply = self._llm.generate_structured(SYSTEM_INSTRUCTION, prompt, RagReply)

        # The model only picks numbers; anything outside 1..n is invalid.
        valid = sorted({n for n in reply.source_numbers if 1 <= n <= len(chunks)})
        dropped = sorted(set(reply.source_numbers) - set(valid))
        # Numbers and scores only, never the question, the chunks or the answer text.
        logger.info(
            "RAG: chunks=%d similarities=%s found=%s cited=%s dropped=%s",
            len(chunks),
            [round(chunk.similarity, 4) for chunk in chunks],
            reply.found,
            valid,
            dropped,
        )

        if not reply.found:
            # Source numbers are ignored: a refusal cites nothing.
            return RagAnswer(
                answer=reply.answer.strip() or UNSUPPORTED_MESSAGE,
                found=False,
                citations=[],
            )

        if not valid or not reply.answer.strip():
            # An answer without a valid citation breaks the core requirement.
            logger.warning("RAG: answer claimed without a valid citation; returning not found")
            return RagAnswer(answer=UNSUPPORTED_MESSAGE, found=False, citations=[])

        return RagAnswer(
            answer=reply.answer.strip(),
            found=True,
            citations=[self._citation(chunks[number - 1]) for number in valid],
        )

    @staticmethod
    def _citation(chunk: RetrievedChunk) -> Citation:
        return Citation(
            document_id=chunk.document_id,
            filename=chunk.filename,
            page_numbers=list(chunk.page_numbers),
            heading=chunk.heading,
            text=chunk.text,
        )
