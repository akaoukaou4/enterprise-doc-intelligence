import uuid

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.db.models import Document, DocumentChunk
from app.services.documents import DocumentService
from app.services.storage import StorageService

PDF = b"%PDF-1.7 integration test file"


@pytest.fixture
def service(settings: Settings, db: Session, storage: StorageService) -> DocumentService:
    return DocumentService(settings, db, storage)


def _add_document(db: Session, storage: StorageService, status: str) -> Document:
    """A real row and a real file. 'processed' by default so the Airflow DAG ignores it."""
    document_id = uuid.uuid4()
    key = f"documents/{document_id}/delete-test.pdf"
    storage.upload(key, PDF, "application/pdf")
    document = Document(
        id=document_id,
        filename="delete-test.pdf",
        storage_key=key,
        content_type="application/pdf",
        size_bytes=len(PDF),
        status=status,
    )
    db.add(document)
    db.commit()
    return document


def _add_chunk(db: Session, document_id: uuid.UUID) -> None:
    vector = [0.0] * 768
    vector[0] = 1.0
    db.add(
        DocumentChunk(
            document_id=document_id,
            chunk_index=0,
            text="delete test chunk",
            page_numbers=[1],
            heading=None,
            embedding=vector,
        )
    )
    db.commit()


def _count(db: Session, model, column, value) -> int:
    return db.scalar(select(func.count()).select_from(model).where(column == value)) or 0


def test_delete_removes_row_chunks_and_file(
    service: DocumentService, db: Session, storage: StorageService
) -> None:
    document = _add_document(db, storage, "processed")
    _add_chunk(db, document.id)
    document_id, key = document.id, document.storage_key

    service.delete(document_id)

    assert _count(db, Document, Document.id, document_id) == 0
    assert _count(db, DocumentChunk, DocumentChunk.document_id, document_id) == 0
    with pytest.raises(NotFoundError):
        storage.download(key)


def test_delete_unknown_document_raises_not_found(service: DocumentService) -> None:
    with pytest.raises(NotFoundError):
        service.delete(uuid.uuid4())


def test_delete_while_processing_is_refused_and_keeps_everything(
    service: DocumentService, db: Session, storage: StorageService
) -> None:
    document = _add_document(db, storage, "processing")
    document_id, key = document.id, document.storage_key
    try:
        with pytest.raises(ConflictError):
            service.delete(document_id)

        assert _count(db, Document, Document.id, document_id) == 1
        assert storage.download(key) == PDF
    finally:
        # Clean up what this test created, using the normal delete path.
        db.execute(update(Document).where(Document.id == document_id).values(status="processed"))
        db.commit()
        service.delete(document_id)
