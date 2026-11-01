import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.db.models import Document
from app.services.document_status import (
    FAILED,
    MAX_ATTEMPTS,
    PROCESSED,
    PROCESSING,
    UPLOADED,
    DocumentStatusService,
)

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def session(engine: Engine):
    """A real session whose commits are all undone at the end: real data stays untouched.

    Inside that transaction every existing document is set to 'processed', so each
    test sees only the documents it creates.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    session.execute(update(Document).values(status=PROCESSED))
    session.commit()

    yield session

    session.close()
    outer.rollback()
    connection.close()


def _add_document(session: Session, status: str, minutes: int = 0, attempts: int = 0) -> uuid.UUID:
    document_id = uuid.uuid4()
    session.add(
        Document(
            id=document_id,
            filename="test.pdf",
            storage_key=f"documents/{document_id}/test.pdf",
            content_type="application/pdf",
            size_bytes=1,
            status=status,
            attempts=attempts,
            created_at=BASE_TIME + timedelta(minutes=minutes),
        )
    )
    session.commit()
    return document_id


def _status(session: Session, document_id: uuid.UUID) -> str | None:
    return session.scalar(select(Document.status).where(Document.id == document_id))


def _attempts(session: Session, document_id: uuid.UUID) -> int | None:
    return session.scalar(select(Document.attempts).where(Document.id == document_id))


def test_claim_takes_the_oldest_first_and_respects_the_limit(session):
    newest = _add_document(session, UPLOADED, minutes=3)
    oldest = _add_document(session, UPLOADED, minutes=1)
    middle = _add_document(session, UPLOADED, minutes=2)

    claimed = DocumentStatusService(session).claim_uploaded(limit=2)

    assert claimed == [oldest, middle]
    assert _status(session, oldest) == PROCESSING
    assert _status(session, middle) == PROCESSING
    assert _status(session, newest) == UPLOADED


def test_claim_ignores_documents_that_are_not_uploaded(session):
    for status in (PROCESSING, PROCESSED, FAILED):
        _add_document(session, status)

    assert DocumentStatusService(session).claim_uploaded(limit=10) == []


def test_claim_never_returns_the_same_document_twice(session):
    only = _add_document(session, UPLOADED)
    service = DocumentStatusService(session)

    assert service.claim_uploaded(limit=10) == [only]
    assert service.claim_uploaded(limit=10) == []


def test_claim_counts_one_attempt_per_claim(session):
    claimed = _add_document(session, UPLOADED, minutes=1)
    waiting = _add_document(session, UPLOADED, minutes=2)

    DocumentStatusService(session).claim_uploaded(limit=1)

    assert _attempts(session, claimed) == 1
    assert _attempts(session, waiting) == 0


def test_reset_orphans_only_touches_processing_documents(session):
    stuck = _add_document(session, PROCESSING)
    done = _add_document(session, PROCESSED)
    broken = _add_document(session, FAILED)

    reset = DocumentStatusService(session).reset_orphans()

    assert reset == 1
    assert _status(session, stuck) == UPLOADED
    assert _status(session, done) == PROCESSED
    assert _status(session, broken) == FAILED


def test_reset_orphans_requeues_a_document_under_the_attempt_limit(session):
    stuck = _add_document(session, PROCESSING, attempts=MAX_ATTEMPTS - 1)

    reset = DocumentStatusService(session).reset_orphans()

    assert reset == 1
    assert _status(session, stuck) == UPLOADED


def test_reset_orphans_marks_a_document_failed_at_the_attempt_limit(session):
    looping = _add_document(session, PROCESSING, attempts=MAX_ATTEMPTS)
    retryable = _add_document(session, PROCESSING, attempts=1)

    reset = DocumentStatusService(session).reset_orphans()

    assert reset == 1  # only the retryable one went back to 'uploaded'
    assert _status(session, looping) == FAILED
    assert _status(session, retryable) == UPLOADED
    # A failed document is never claimed again.
    assert DocumentStatusService(session).claim_uploaded(limit=10) == [retryable]


def test_mark_methods_set_the_status(session):
    document_id = _add_document(session, UPLOADED)
    service = DocumentStatusService(session)

    service.mark_processing(document_id)
    assert _status(session, document_id) == PROCESSING

    service.mark_processed(document_id)
    assert _status(session, document_id) == PROCESSED

    service.mark_failed(document_id)
    assert _status(session, document_id) == FAILED
