import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Document
from app.services.documents import DocumentService
from app.services.storage import StorageService

# Test documents are dated far in the future, so they always sort first,
# whatever else is in the database.
FUTURE = datetime(2099, 1, 1, tzinfo=UTC)


def _document(name: str, created_at: datetime, document_id: uuid.UUID) -> Document:
    return Document(
        id=document_id,
        filename=name,
        storage_key=f"documents/{document_id}/{name}",
        content_type="application/pdf",
        size_bytes=1,
        # "processed", so the Airflow DAG never claims these fake documents.
        status="processed",
        created_at=created_at,
    )


@pytest.fixture
def service(settings: Settings, db: Session, storage: StorageService) -> DocumentService:
    return DocumentService(settings, db, storage)


@pytest.fixture
def seeded(db: Session) -> list[Document]:
    """Three documents in the expected order: newest first, then the id breaks a tie."""
    newest = _document("newest.pdf", FUTURE + timedelta(days=2), uuid.UUID(int=3))
    tie_low = _document("tie-low.pdf", FUTURE, uuid.UUID(int=1))
    tie_high = _document("tie-high.pdf", FUTURE, uuid.UUID(int=2))
    db.add_all([newest, tie_high, tie_low])
    db.commit()
    return [newest, tie_low, tie_high]


def test_list_is_newest_first_and_id_breaks_ties(
    service: DocumentService, seeded: list[Document]
) -> None:
    documents, _ = service.list_documents(limit=3, offset=0)

    assert [d.id for d in documents] == [d.id for d in seeded]


def test_total_counts_all_documents_not_the_page(service: DocumentService, db: Session) -> None:
    _, before = service.list_documents(limit=1, offset=0)
    db.add_all(
        [
            _document("one.pdf", FUTURE, uuid.UUID(int=1)),
            _document("two.pdf", FUTURE, uuid.UUID(int=2)),
        ]
    )
    db.commit()

    documents, after = service.list_documents(limit=1, offset=0)

    assert len(documents) == 1
    assert after == before + 2


def test_pages_do_not_overlap_or_skip(service: DocumentService, seeded: list[Document]) -> None:
    first, _ = service.list_documents(limit=2, offset=0)
    second, _ = service.list_documents(limit=2, offset=2)

    assert [d.id for d in first] == [seeded[0].id, seeded[1].id]
    assert second[0].id == seeded[2].id
    assert not {d.id for d in first} & {d.id for d in second}


def test_offset_past_the_end_returns_empty_page(
    service: DocumentService, seeded: list[Document]
) -> None:
    _, total = service.list_documents(limit=1, offset=0)

    documents, same_total = service.list_documents(limit=5, offset=total + 10)

    assert documents == []
    assert same_total == total
