import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    """One uploaded PDF.

    The file itself lives in object storage (MinIO / S3). This row stores
    where it is (`storage_key`) and where it is in the processing workflow.
    """

    __tablename__ = "documents"

    # Generated in Python so the ID exists before the insert and can be
    # used to build the storage key.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)

    # uploaded -> processing -> processed | failed
    # A plain string rather than a Postgres ENUM: ENUMs are awkward to
    # change in migrations. The application enforces the allowed values.
    status: Mapped[str] = mapped_column(String(20), default="uploaded", server_default="uploaded")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
