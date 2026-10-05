import uuid

import pytest

from app.core.config import Settings
from app.core.errors import ExternalServiceError, NotFoundError, ValidationFailedError
from app.db.models import Document
from app.services.documents import DocumentService

PDF = b"%PDF-1.7 fake pdf content"


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.fail_upload = False

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        if self.fail_upload:
            raise ExternalServiceError("Object storage request failed.")
        self.uploaded[key] = data

    def delete(self, key: str) -> None:
        self.deleted.append(key)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[Document] = []
        self.rolled_back = False
        self.fail_commit = False
        self.existing: Document | None = None

    def add(self, obj: Document) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        if self.fail_commit:
            raise RuntimeError("db down")

    def rollback(self) -> None:
        self.rolled_back = True

    def refresh(self, obj: Document) -> None:
        pass

    def get(self, model, document_id):
        return self.existing


def _service(db: FakeSession, storage: FakeStorage, max_upload_mb: int = 1) -> DocumentService:
    settings = Settings(_env_file=None, max_upload_mb=max_upload_mb)
    return DocumentService(settings, db, storage)  # type: ignore[arg-type]


def test_create_uploads_file_and_inserts_row() -> None:
    db, storage = FakeSession(), FakeStorage()

    document = _service(db, storage).create("policy.pdf", "application/pdf", PDF)

    assert document.filename == "policy.pdf"
    assert document.size_bytes == len(PDF)
    assert document.status == "uploaded"
    assert document.storage_key == f"documents/{document.id}/policy.pdf"
    assert storage.uploaded[document.storage_key] == PDF
    assert db.added == [document]


def test_create_strips_path_from_filename() -> None:
    document = _service(FakeSession(), FakeStorage()).create(
        "C:\\Users\\me\\policy.pdf", "application/pdf", PDF
    )

    assert document.filename == "policy.pdf"


def test_create_rejects_non_pdf_content_type() -> None:
    with pytest.raises(ValidationFailedError):
        _service(FakeSession(), FakeStorage()).create("a.txt", "text/plain", PDF)


def test_create_rejects_empty_file() -> None:
    with pytest.raises(ValidationFailedError):
        _service(FakeSession(), FakeStorage()).create("a.pdf", "application/pdf", b"")


def test_create_rejects_file_that_is_not_really_a_pdf() -> None:
    with pytest.raises(ValidationFailedError):
        _service(FakeSession(), FakeStorage()).create("a.pdf", "application/pdf", b"not a pdf")


def test_create_rejects_file_over_size_limit() -> None:
    too_big = PDF + b"x" * (1024 * 1024)

    with pytest.raises(ValidationFailedError):
        _service(FakeSession(), FakeStorage()).create("a.pdf", "application/pdf", too_big)


def test_storage_failure_creates_no_row() -> None:
    db, storage = FakeSession(), FakeStorage()
    storage.fail_upload = True

    with pytest.raises(ExternalServiceError):
        _service(db, storage).create("a.pdf", "application/pdf", PDF)

    assert db.added == []


def test_database_failure_removes_uploaded_file() -> None:
    db, storage = FakeSession(), FakeStorage()
    db.fail_commit = True

    with pytest.raises(RuntimeError):
        _service(db, storage).create("a.pdf", "application/pdf", PDF)

    assert db.rolled_back is True
    assert len(storage.uploaded) == 1
    assert storage.deleted == list(storage.uploaded)


def test_get_returns_existing_document() -> None:
    db = FakeSession()
    db.existing = Document(id=uuid.uuid4(), filename="a.pdf")

    assert _service(db, FakeStorage()).get(db.existing.id) is db.existing


def test_get_missing_document_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        _service(FakeSession(), FakeStorage()).get(uuid.uuid4())
