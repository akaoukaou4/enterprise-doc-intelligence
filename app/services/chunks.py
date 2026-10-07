"""Stores a document's chunks and their embeddings in PostgreSQL (pgvector).

The embedding service produces the vectors; this service only stores them.
Keeping the two apart means storage can be tested without loading the model.
"""

import logging
import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import EMBEDDING_DIMENSIONS, Document, DocumentChunk
from app.pipeline.models import Chunk

logger = logging.getLogger(__name__)


class ChunkService:
    """Writes chunks with provenance (pages, heading) and vectors to the database."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def replace_chunks(
        self,
        document_id: uuid.UUID,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> int:
        """Replace all chunks of a document with new ones. Returns how many were stored.

        Delete and insert happen in one transaction: if anything fails, the
        previous chunks are still there. An empty list removes all chunks.
        """
        self._validate(chunks, vectors)

        if self._db.get(Document, document_id) is None:
            raise NotFoundError(f"Document not found: {document_id}")

        rows = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=index,
                text=chunk.text,
                page_numbers=list(chunk.page_numbers),
                heading=chunk.heading,
                embedding=vector,
            )
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]

        try:
            self._db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            self._db.add_all(rows)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        logger.info("Stored %d chunks for document %s", len(rows), document_id)
        return len(rows)

    @staticmethod
    def _validate(chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(f"Got {len(chunks)} chunks but {len(vectors)} vectors.")
        for index, vector in enumerate(vectors):
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Chunk {index} has a vector of size {len(vector)}, "
                    f"expected {EMBEDDING_DIMENSIONS}."
                )
