import logging
import uuid
from pathlib import PurePath

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.db.models import Document
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

PDF_CONTENT_TYPE = "application/pdf"
PDF_MAGIC = b"%PDF-"
MAX_FILENAME_LENGTH = 255

# Page size of the list endpoint. A maximum protects the database; the API
# returns 422 outside the range, and the service refuses it too.
DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100


class DocumentService:
    """Stores an uploaded PDF in object storage and records it in PostgreSQL."""

    def __init__(self, settings: Settings, db: Session, storage: StorageService) -> None:
        self._settings = settings
        self._db = db
        self._storage = storage

    def create(self, filename: str | None, content_type: str | None, data: bytes) -> Document:
        self._validate(content_type, data)

        document_id = uuid.uuid4()
        name = self._safe_filename(filename)
        storage_key = f"documents/{document_id}/{name}"

        # 1. File first. If this fails, no row exists.
        self._storage.upload(storage_key, data, PDF_CONTENT_TYPE)

        # 2. Then the row. If this fails, remove the file so nothing is orphaned.
        document = Document(
            id=document_id,
            filename=name,
            storage_key=storage_key,
            content_type=PDF_CONTENT_TYPE,
            size_bytes=len(data),
            status="uploaded",
        )
        try:
            self._db.add(document)
            self._db.commit()
        except Exception:
            self._db.rollback()
            self._remove_orphan(storage_key)
            raise

        # Loads created_at, which the database fills in.
        self._db.refresh(document)
        return document

    def get(self, document_id: uuid.UUID) -> Document:
        document = self._db.get(Document, document_id)
        if document is None:
            raise NotFoundError(f"Document not found: {document_id}")
        return document

    def delete(self, document_id: uuid.UUID) -> None:
        """Delete the row (chunks cascade), then the file (D-50)."""
        # Lock the row so a worker cannot claim it while we decide.
        document = self._db.get(Document, document_id, with_for_update=True)
        if document is None:
            raise NotFoundError(f"Document not found: {document_id}")
        if document.status == "processing":
            self._db.rollback()  # release the lock
            raise ConflictError("The document is being processed. Try again when it is done.")

        storage_key = document.storage_key
        try:
            self._db.delete(document)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        # Row first. A leftover file is harmless; a row without a file is not.
        self._remove_orphan(storage_key)

    def list_documents(
        self, limit: int = DEFAULT_LIST_LIMIT, offset: int = 0
    ) -> tuple[list[Document], int]:
        """Return one page of documents, newest first, and the total count."""
        if not 1 <= limit <= MAX_LIST_LIMIT:
            raise ValidationFailedError(f"limit must be between 1 and {MAX_LIST_LIMIT}")
        if offset < 0:
            raise ValidationFailedError("offset must be 0 or more")

        total = self._db.scalar(select(func.count()).select_from(Document)) or 0
        # id breaks ties, so two pages never overlap or skip a document.
        rows = self._db.scalars(
            select(Document)
            .order_by(Document.created_at.desc(), Document.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return list(rows), total

    def _validate(self, content_type: str | None, data: bytes) -> None:
        if content_type != PDF_CONTENT_TYPE:
            raise ValidationFailedError("Only PDF files are accepted.")
        if not data:
            raise ValidationFailedError("The uploaded file is empty.")
        max_bytes = self._settings.max_upload_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise ValidationFailedError(
                f"The file is larger than the {self._settings.max_upload_mb} MB limit."
            )
        # A client can lie about the content type, so check the file itself.
        if not data.startswith(PDF_MAGIC):
            raise ValidationFailedError("The file does not look like a valid PDF.")

    @staticmethod
    def _safe_filename(filename: str | None) -> str:
        # Keep only the last path component; browsers can send full paths.
        name = PurePath((filename or "").replace("\\", "/")).name.strip()
        return name[:MAX_FILENAME_LENGTH] or "document.pdf"

    def _remove_orphan(self, storage_key: str) -> None:
        try:
            self._storage.delete(storage_key)
        except Exception:
            # Cleanup is best effort; the original database error is what matters.
            logger.exception("Could not remove orphaned file %s", storage_key)
