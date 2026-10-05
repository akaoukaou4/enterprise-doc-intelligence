import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.deps import get_document_service
from app.core.errors import NotFoundError, ValidationFailedError
from app.db.models import Document
from app.main import create_app


class FakeDocumentService:
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


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()
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
