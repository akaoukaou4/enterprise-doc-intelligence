import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Output size of google/embeddinggemma-300m. The database enforces it: a vector
# of any other size is rejected on insert. Changing the embedding model to one
# with a different size means a new migration.
EMBEDDING_DIMENSIONS = 768


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


class DocumentChunk(Base):
    """One searchable piece of a document, with its embedding and provenance.

    `page_numbers` and `heading` are what citations are built from, so they
    are stored next to the vector, not looked up later.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        # Processing the same document twice must not create duplicate chunks.
        # The index behind this constraint also serves "all chunks of a document".
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_document_id_chunk_index"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)

    text: Mapped[str] = mapped_column(Text)
    # A chunk can span pages, e.g. [2, 3].
    page_numbers: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    heading: Mapped[str | None] = mapped_column(Text)

    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
