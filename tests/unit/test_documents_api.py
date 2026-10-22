import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_document_service
from app.core.errors import NotFoundError, ValidationFailedError
from app.db.models import Document
from app.main import create_app


def _document(filename: str) -> Document:
    return Document(
        id=uuid.uuid4(),
        filename=filename,
        storage_key="k",
        content_type="application/pdf",
        size_bytes=10,
        status="uploaded",
        created_at=datetime.now(UTC),
    )


class FakeDocumentService:
    def __init__(self) -> None:
        self.list_calls: list[tuple[int, int]] = []

    def create(self, filename, content_type, data):
        if content_type != "application/pdf":
            raise ValidationFailedError("Only PDF files are accepted.")
        return Document(
            id=uuid.uuid4(),
            filename=filename,
            storage_key="k",
            content_type=content_type,
            size_bytes=len(data),
            status="uploaded",
            created_at=datetime.now(UTC),
        )

    def get(self, document_id):
        raise NotFoundError(f"Document not found: {document_id}")

    def list_documents(self, limit, offset):
        self.list_calls.append((limit, offset))
        # Two documents on the page, seven in total.
        return [_document("b.pdf"), _document("a.pdf")], 7


def _client(service: FakeDocumentService | None = None) -> TestClient:
    app = create_app()
    fake = service or FakeDocumentService()
    app.dependency_overrides[get_document_service] = lambda: fake
    return TestClient(app)


def test_upload_returns_201_and_metadata() -> None:
    response = _client().post(
        "/api/v1/documents",
        files={"file": ("policy.pdf", b"%PDF-1.7 x", "application/pdf")},
    )

    body = response.json()
    assert response.status_code == 201
    assert body["filename"] == "policy.pdf"
    assert body["status"] == "uploaded"
    assert "storage_key" not in body


def test_upload_non_pdf_returns_422_with_error_shape() -> None:
    response = _client().post(
        "/api/v1/documents",
        files={"file": ("a.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


def test_upload_without_file_returns_422() -> None:
    assert _client().post("/api/v1/documents").status_code == 422


def test_get_unknown_document_returns_404() -> None:
    response = _client().get(f"/api/v1/documents/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_list_returns_page_envelope_with_defaults() -> None:
    service = FakeDocumentService()

    response = _client(service).get("/api/v1/documents")

    body = response.json()
    assert response.status_code == 200
    assert [item["filename"] for item in body["items"]] == ["b.pdf", "a.pdf"]
    assert body["total"] == 7
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert "storage_key" not in body["items"][0]
    assert service.list_calls == [(20, 0)]


def test_list_passes_limit_and_offset_to_the_service() -> None:
    service = FakeDocumentService()

    response = _client(service).get("/api/v1/documents?limit=5&offset=10")

    assert response.status_code == 200
    assert response.json()["limit"] == 5
    assert response.json()["offset"] == 10
    assert service.list_calls == [(5, 10)]


def test_list_accepts_the_maximum_limit() -> None:
    assert _client().get("/api/v1/documents?limit=100").status_code == 200


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=abc"])
def test_list_rejects_bad_paging_with_422(query: str) -> None:
    service = FakeDocumentService()

    response = _client(service).get(f"/api/v1/documents?{query}")

    assert response.status_code == 422
    assert "error" in response.json()
    assert service.list_calls == []  # the service is never reached
