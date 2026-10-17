import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_retrieval_service
from app.main import create_app
from app.services.retrieval import RetrievedChunk


class FakeRetrievalService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def search(self, question: str, top_k: int) -> list[RetrievedChunk]:
        self.calls.append((question, top_k))
        return [
            RetrievedChunk(
                document_id=uuid.uuid4(),
                filename="policy.pdf",
                page_numbers=[3, 4],
                heading="Incident handling",
                text="Report the incident within 24 hours.",
                similarity=0.62,
            )
        ]


def _client(service: FakeRetrievalService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_retrieval_service] = lambda: service
    return TestClient(app)


def test_search_returns_hits_with_citation_fields() -> None:
    service = FakeRetrievalService()

    response = _client(service).post(
        "/api/v1/search", json={"question": "  How do I report an incident?  ", "top_k": 3}
    )

    hit = response.json()["results"][0]
    assert response.status_code == 200
    assert hit["filename"] == "policy.pdf"
    assert hit["page_numbers"] == [3, 4]
    assert hit["heading"] == "Incident handling"
    assert hit["similarity"] == 0.62
    assert service.calls == [("How do I report an incident?", 3)]


def test_search_uses_default_top_k() -> None:
    service = FakeRetrievalService()

    _client(service).post("/api/v1/search", json={"question": "anything"})

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
    service = FakeRetrievalService()

    response = _client(service).post("/api/v1/search", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert service.calls == []
