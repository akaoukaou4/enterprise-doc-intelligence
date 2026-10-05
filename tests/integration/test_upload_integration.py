import uuid

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.db.models import Document
from app.services.documents import DocumentService
from app.services.storage import StorageService

PDF = b"%PDF-1.7 integration test content"


def _row_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Document)) or 0


def test_upload_is_stored_in_minio_and_postgres(
    settings: Settings, engine: Engine, db: Session, storage: StorageService
) -> None:
    service = DocumentService(settings, db, storage)

    document = service.create("it-policy.pdf", "application/pdf", PDF)

    # The file is really in MinIO, with the exact bytes.
    assert storage.download(document.storage_key) == PDF

    # The row is really committed: read it from a different session.
    with Session(engine) as other:
        row = other.get(Document, document.id)
        assert row is not None
        assert row.filename == "it-policy.pdf"
        assert row.size_bytes == len(PDF)
        assert row.status == "uploaded"
        assert row.created_at is not None


def test_rejected_upload_leaves_no_row(
    settings: Settings, db: Session, storage: StorageService
) -> None:
    service = DocumentService(settings, db, storage)
    before = _row_count(db)

    with pytest.raises(ValidationFailedError):
        service.create("fake.pdf", "application/pdf", b"not a pdf")

    assert _row_count(db) == before


def test_failed_insert_removes_uploaded_file(
    settings: Settings,
    db: Session,
    storage: StorageService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = DocumentService(settings, db, storage)
    uploaded_keys: list[str] = []
    real_upload = storage.upload

    def recording_upload(key: str, data: bytes, content_type: str) -> None:
        uploaded_keys.append(key)
        real_upload(key, data, content_type)

    def failing_commit() -> None:
        raise RuntimeError("simulated database failure")

    before = _row_count(db)

    with monkeypatch.context() as patch:
        patch.setattr(storage, "upload", recording_upload)
        patch.setattr(db, "commit", failing_commit)
        with pytest.raises(RuntimeError):
            service.create("orphan.pdf", "application/pdf", PDF)

    # The file reached MinIO, then the service removed it again.
    assert len(uploaded_keys) == 1
    with pytest.raises(NotFoundError):
        storage.download(uploaded_keys[0])
    assert _row_count(db) == before


def test_storage_key_must_be_unique(db: Session) -> None:
    key = f"documents/{uuid.uuid4()}/same.pdf"

    def make_document() -> Document:
        return Document(
            id=uuid.uuid4(),
            filename="same.pdf",
            storage_key=key,
            content_type="application/pdf",
            size_bytes=1,
        )

    db.add(make_document())
    db.commit()

    db.add(make_document())
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
