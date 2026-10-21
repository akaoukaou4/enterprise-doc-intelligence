"""Document lifecycle: uploaded -> processing -> processed | failed.

Every status change goes through this module, so `documents.status` always says
what really happened. `DocumentStatusService` talks to PostgreSQL; `IngestionRunner`
wraps one ingestion and records its outcome. Airflow, the single-document script
and the folder script all use the runner.
"""

import logging
import uuid
from typing import TYPE_CHECKING, Protocol

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Document

if TYPE_CHECKING:
    from app.services.ingestion import IngestionResult

logger = logging.getLogger(__name__)

UPLOADED = "uploaded"
PROCESSING = "processing"
PROCESSED = "processed"
FAILED = "failed"


class DocumentStatusService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def reset_orphans(self) -> int:
        """Turn documents left in 'processing' back into 'uploaded'.

        Only safe when no ingestion is running: a killed worker never records its
        outcome, so its document would stay 'processing' forever.
        """
        result = self._db.execute(
            update(Document).where(Document.status == PROCESSING).values(status=UPLOADED)
        )
        self._db.commit()
        return result.rowcount

    def claim_uploaded(self, limit: int) -> list[uuid.UUID]:
        """Move up to `limit` uploaded documents (oldest first) to 'processing'.

        SKIP LOCKED means two callers at the same time never claim the same row.
        """
        ids = list(
            self._db.scalars(
                select(Document.id)
                .where(Document.status == UPLOADED)
                .order_by(Document.created_at, Document.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        if ids:
            self._db.execute(update(Document).where(Document.id.in_(ids)).values(status=PROCESSING))
        self._db.commit()
        return ids

    def mark_processing(self, document_id: uuid.UUID) -> None:
        self._set(document_id, PROCESSING)

    def mark_processed(self, document_id: uuid.UUID) -> None:
        self._set(document_id, PROCESSED)

    def mark_failed(self, document_id: uuid.UUID) -> None:
        # The error may have left the session inside a failed transaction.
        self._db.rollback()
        self._set(document_id, FAILED)

    def _set(self, document_id: uuid.UUID, status: str) -> None:
        self._db.execute(update(Document).where(Document.id == document_id).values(status=status))
        self._db.commit()


class StatusRecorder(Protocol):
    def mark_processing(self, document_id: uuid.UUID) -> None: ...
    def mark_processed(self, document_id: uuid.UUID) -> None: ...
    def mark_failed(self, document_id: uuid.UUID) -> None: ...


class Ingestor(Protocol):
    def ingest(self, document: Document) -> "IngestionResult": ...


class IngestionRunner:
    """Runs one ingestion and records its outcome in `documents.status`."""

    def __init__(self, ingestion: Ingestor, statuses: StatusRecorder) -> None:
        self._ingestion = ingestion
        self._statuses = statuses

    def run(self, document: Document) -> "IngestionResult":
        document_id = document.id
        self._statuses.mark_processing(document_id)
        try:
            result = self._ingestion.ingest(document)
        except Exception:
            self._record_failure(document_id)
            raise
        self._statuses.mark_processed(document_id)
        return result

    def _record_failure(self, document_id: uuid.UUID) -> None:
        # The original error is what matters; never let this hide it.
        try:
            self._statuses.mark_failed(document_id)
        except Exception:
            logger.exception("Could not record failed status for %s", document_id)
