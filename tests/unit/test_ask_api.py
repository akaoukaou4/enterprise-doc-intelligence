import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_rag_service
from app.core.errors import ExternalServiceError
from app.main import create_app
from app.services.rag import Citation, RagAnswer


class FakeRagService:
    def __init__(self, answer: RagAnswer | None = None, error: Exception | None = None) -> None:
        self._answer = answer
        self._error = error
        self.calls: list[tuple[str, int]] = []

    def ask(self, question: str, top_k: int) -> RagAnswer:
        self.calls.append((question, top_k))
        if self._error:
            raise self._error
        return self._answer


def _client(service: FakeRagService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_rag_service] = lambda: service
    return TestClient(app)


def _found_answer() -> RagAnswer:
    return RagAnswer(
        answer="Report the incident within 24 hours.",
        found=True,
        citations=[
            Citation(
                document_id=uuid.uuid4(),
                filename="policy.pdf",
                page_numbers=[3, 4],
                heading="Incident handling",
                text="Report the incident within 24 hours.",
            )
        ],
    )


def test_ask_returns_answer_with_citation_fields() -> None:
    service = FakeRagService(_found_answer())

    response = _client(service).post(
        "/api/v1/ask", json={"question": "  How do I report an incident?  ", "top_k": 3}
    )

    body = response.json()
    assert response.status_code == 200
    assert body["found"] is True
    assert body["answer"] == "Report the incident within 24 hours."
    citation = body["citations"][0]
    assert citation["filename"] == "policy.pdf"
    assert citation["page_numbers"] == [3, 4]
    assert citation["heading"] == "Incident handling"
    assert citation["text"] == "Report the incident within 24 hours."
    assert "document_id" in citation
    assert service.calls == [("How do I report an incident?", 3)]


def test_ask_not_found_has_no_citations() -> None:
    service = FakeRagService(
        RagAnswer(answer="The documents do not say.", found=False, citations=[])
    )

    response = _client(service).post("/api/v1/ask", json={"question": "anything"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "The documents do not say.",
        "found": False,
        "citations": [],
    }


def test_ask_uses_default_top_k() -> None:
    service = FakeRagService(_found_answer())

    _client(service).post("/api/v1/ask", json={"question": "anything"})

    assert service.calls == [("anything", 8)]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 1001},
        {"question": "ok", "top_k": 0},
        {"question": "ok", "top_k": 21},
    ],
)
def test_invalid_body_returns_422_with_error_shape(body: dict) -> None:
    service = FakeRagService(_found_answer())

    response = _client(service).post("/api/v1/ask", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert service.calls == []


def test_gemini_failure_returns_502_with_error_shape() -> None:
    service = FakeRagService(error=ExternalServiceError("The AI service request failed."))

    response = _client(service).post("/api/v1/ask", json={"question": "anything"})

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "external_service_error",
            "message": "The AI service request failed.",
        }
    }
