import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.db.models import Document, DocumentChunk
from app.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 8
MAX_TOP_K = 20
MAX_QUESTION_CHARS = 1000


@dataclass(frozen=True)
class RetrievedChunk:
    """One search hit, with everything a citation needs (no second lookup)."""

    document_id: uuid.UUID
    filename: str
    page_numbers: list[int]
    heading: str | None
    text: str
    similarity: float


class RetrievalService:
    """Dense retrieval: embed the question, find the nearest chunks in pgvector."""

    def __init__(self, db: Session, embeddings: EmbeddingService) -> None:
        self._db = db
        self._embeddings = embeddings

    def search(self, question: str, top_k: int = DEFAULT_TOP_K) -> list[RetrievedChunk]:
        question = question.strip()
        if not question:
            raise ValidationFailedError("The question must not be empty.")
        if len(question) > MAX_QUESTION_CHARS:
            raise ValidationFailedError(
                f"The question is longer than {MAX_QUESTION_CHARS} characters."
            )
        if not 1 <= top_k <= MAX_TOP_K:
            raise ValidationFailedError(f"top_k must be between 1 and {MAX_TOP_K}.")

        query_vector = self._embeddings.embed_query(question)

        # Vectors are normalized, so similarity = 1 - cosine distance.
        distance = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
        statement = (
            select(DocumentChunk, Document.filename, distance)
            .join(Document, Document.id == DocumentChunk.document_id)
            .order_by(distance, DocumentChunk.document_id, DocumentChunk.chunk_index)
            .limit(top_k)
        )
        rows = self._db.execute(statement).all()

        results = [
            RetrievedChunk(
                document_id=chunk.document_id,
                filename=filename,
                page_numbers=list(chunk.page_numbers),
                heading=chunk.heading,
                text=chunk.text,
                similarity=1.0 - float(dist),
            )
            for chunk, filename, dist in rows
        ]
        logger.info("Retrieved %d chunks (top_k=%d)", len(results), top_k)
        return results
