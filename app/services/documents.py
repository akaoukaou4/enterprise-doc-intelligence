import logging
import uuid
from pathlib import PurePath

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.db.models import Document
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

PDF_CONTENT_TYPE = "application/pdf"
PDF_MAGIC = b"%PDF-"
MAX_FILENAME_LENGTH = 255


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
