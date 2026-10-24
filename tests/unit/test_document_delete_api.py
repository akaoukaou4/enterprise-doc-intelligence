import uuid

from fastapi.testclient import TestClient

from app.api.deps import get_document_service
from app.core.errors import ConflictError, NotFoundError
from app.main import create_app

BUSY_ID = uuid.uuid4()


class FakeDocumentService:
    def __init__(self) -> None:
        self.deleted: list[uuid.UUID] = []

    def delete(self, document_id: uuid.UUID) -> None:
        if document_id == BUSY_ID:
            raise ConflictError("The document is being processed.")
        if str(document_id).startswith("00000000"):
            raise NotFoundError(f"Document not found: {document_id}")
        self.deleted.append(document_id)


def _client(service: FakeDocumentService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_document_service] = lambda: service
    return TestClient(app)


def test_delete_returns_204_with_no_body() -> None:
    service = FakeDocumentService()
    document_id = uuid.uuid4()

    response = _client(service).delete(f"/api/v1/documents/{document_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert service.deleted == [document_id]


def test_delete_unknown_document_returns_404() -> None:
    response = _client(FakeDocumentService()).delete(f"/api/v1/documents/{uuid.UUID(int=1)}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_delete_while_processing_returns_409() -> None:
    response = _client(FakeDocumentService()).delete(f"/api/v1/documents/{BUSY_ID}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_delete_with_a_bad_id_returns_422() -> None:
    response = _client(FakeDocumentService()).delete("/api/v1/documents/not-a-uuid")

    assert response.status_code == 422
