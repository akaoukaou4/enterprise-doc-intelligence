import uuid

import pytest

from app.core.errors import ExternalServiceError
from app.services.rag import (
    NO_DOCUMENTS_MESSAGE,
    UNSUPPORTED_MESSAGE,
    RagService,
)
from app.services.rag_prompt import SYSTEM_INSTRUCTION, RagReply
from app.services.retrieval import DEFAULT_TOP_K, RetrievedChunk


def make_chunk(number: int) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=uuid.uuid4(),
        filename=f"doc{number}.pdf",
        page_numbers=[number, number + 1],
        heading=f"Heading {number}",
        text=f"Text of chunk {number}.",
        similarity=0.5,
    )


class FakeRetrieval:
    def __init__(self, chunks: list[RetrievedChunk] | None = None, error=None) -> None:
        self._chunks = chunks or []
        self._error = error
        self.calls: list[tuple[str, int]] = []

    def search(self, question: str, top_k: int) -> list[RetrievedChunk]:
        self.calls.append((question, top_k))
        if self._error:
            raise self._error
        return self._chunks


class FakeLlm:
    def __init__(self, reply: RagReply | None = None, error=None) -> None:
        self._reply = reply
        self._error = error
        self.calls: list[dict] = []

    def generate_structured(self, system_instruction, prompt, response_model):
        self.calls.append(
            {
                "system_instruction": system_instruction,
                "prompt": prompt,
                "response_model": response_model,
            }
        )
        if self._error:
            raise self._error
        return self._reply


def make_service(chunks=None, reply=None, retrieval_error=None, llm_error=None):
    retrieval = FakeRetrieval(chunks, error=retrieval_error)
    llm = FakeLlm(reply, error=llm_error)
    return RagService(retrieval, llm), retrieval, llm


def reply(found=True, answer="The answer.", numbers=None) -> RagReply:
    return RagReply(found=found, answer=answer, source_numbers=numbers or [])


def test_citations_map_to_the_chunks_the_model_used() -> None:
    chunks = [make_chunk(1), make_chunk(2), make_chunk(3)]
    service, _, _ = make_service(chunks, reply(numbers=[3, 1, 3]))

    result = service.ask("What is it?")

    assert result.found is True
    assert result.answer == "The answer."
    assert len(result.citations) == 2
    first, third = result.citations
    assert first.document_id == chunks[0].document_id
    assert first.filename == "doc1.pdf"
    assert first.page_numbers == [1, 2]
    assert first.heading == "Heading 1"
    assert first.text == "Text of chunk 1."
    assert third.document_id == chunks[2].document_id
    assert third.page_numbers == [3, 4]


def test_request_to_the_llm_contains_rules_sources_and_question() -> None:
    service, _, llm = make_service([make_chunk(1)], reply(numbers=[1]))

    service.ask("  What is it?  ")

    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["system_instruction"] == SYSTEM_INSTRUCTION
    assert call["response_model"] is RagReply
    assert '<source number="1">' in call["prompt"]
    assert "Text of chunk 1." in call["prompt"]
    assert "What is it?" in call["prompt"]


def test_no_chunks_means_no_gemini_call() -> None:
    service, _, llm = make_service([], reply(numbers=[1]))

    result = service.ask("What is it?")

    assert result.found is False
    assert result.citations == []
    assert result.answer == NO_DOCUMENTS_MESSAGE
    assert llm.calls == []


def test_not_found_has_no_citations_even_if_numbers_are_listed() -> None:
    service, _, _ = make_service(
        [make_chunk(1), make_chunk(2)],
        reply(found=False, answer="The documents do not say.", numbers=[1, 2]),
    )

    result = service.ask("What is it?")

    assert result.found is False
    assert result.answer == "The documents do not say."
    assert result.citations == []


def test_not_found_with_a_blank_answer_gets_a_fallback_message() -> None:
    service, _, _ = make_service([make_chunk(1)], reply(found=False, answer="   "))

    result = service.ask("What is it?")

    assert result.found is False
    assert result.answer == UNSUPPORTED_MESSAGE


def test_invalid_source_numbers_are_dropped() -> None:
    chunks = [make_chunk(1), make_chunk(2)]
    service, _, _ = make_service(chunks, reply(numbers=[1, 99, 0, -1]))

    result = service.ask("What is it?")

    assert result.found is True
    assert [c.filename for c in result.citations] == ["doc1.pdf"]


@pytest.mark.parametrize(
    "model_reply",
    [
        pytest.param(reply(numbers=[]), id="no_numbers"),
        pytest.param(reply(numbers=[0, 99, -1]), id="only_invalid_numbers"),
        pytest.param(reply(answer="   ", numbers=[1]), id="blank_answer"),
    ],
)
def test_claimed_answer_without_valid_citation_is_not_found(model_reply: RagReply) -> None:
    service, _, _ = make_service([make_chunk(1), make_chunk(2)], model_reply)

    result = service.ask("What is it?")

    assert result.found is False
    assert result.citations == []
    assert result.answer == UNSUPPORTED_MESSAGE


def test_llm_failure_is_not_swallowed() -> None:
    service, _, _ = make_service(
        [make_chunk(1)], llm_error=ExternalServiceError("The AI service request failed.")
    )

    with pytest.raises(ExternalServiceError):
        service.ask("What is it?")


def test_invalid_input_from_retrieval_is_not_swallowed() -> None:
    service, _, llm = make_service(retrieval_error=ValueError("bad input"))

    with pytest.raises(ValueError, match="bad input"):
        service.ask("What is it?")

    assert llm.calls == []


def test_top_k_defaults_to_the_retrieval_default() -> None:
    service, retrieval, _ = make_service([make_chunk(1)], reply(numbers=[1]))

    service.ask("What is it?")

    assert retrieval.calls == [("What is it?", DEFAULT_TOP_K)]


def test_top_k_is_passed_through() -> None:
    service, retrieval, _ = make_service([make_chunk(1)], reply(numbers=[1]))

    service.ask("What is it?", top_k=3)

    assert retrieval.calls == [("What is it?", 3)]
