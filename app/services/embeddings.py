"""Embeddings with EmbeddingGemma (through sentence-transformers).

The model is trained for two kinds of text, formatted differently:

* documents: "title: <title or none> | text: <content>"
* queries:   "task: search result | query: <question>"

Retrieval only works well when documents and queries are embedded the way the
model expects. The vectors have length 1 (the model normalizes them), so
cosine similarity is a plain dot product.
"""

import logging
import threading
import time
from typing import Any

from app.core.config import Settings
from app.db.models import EMBEDDING_DIMENSIONS
from app.pipeline.models import Chunk

logger = logging.getLogger(__name__)


def build_document_text(chunk: Chunk) -> str:
    """The exact string we embed for a chunk: its heading acts as the title.

    The model's own encode_document() always writes "title: none", so we build
    the string ourselves to be able to pass the real heading. Without a
    heading the result is identical to encode_document().
    """
    title = chunk.heading or "none"
    return f"title: {title} | text: {chunk.text}"


class EmbeddingService:
    """Turns chunks and questions into vectors. Loads the model once, on demand."""

    def __init__(self, settings: Settings, model: Any | None = None) -> None:
        self._settings = settings
        # Tests pass a fake model; in the app it is loaded on first use or by
        # the background preload at startup (D-49).
        self._model = model
        self._checked = False
        self._loading = False
        # One load at a time: a preload and an early question must never load
        # the model twice (that would double its memory).
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        """Return ready, loading or idle (not loaded yet). Never starts a load."""
        if self._checked:
            return "ready"
        return "loading" if self._loading else "idle"

    def load(self) -> None:
        """Load the model now. Safe to call from several threads at once."""
        self._get_model()

    def embed_documents(self, chunks: list[Chunk]) -> list[list[float]]:
        """One vector per chunk, in the same order."""
        if not chunks:
            return []
        texts = [build_document_text(chunk) for chunk in chunks]
        vectors = self._get_model().encode(texts, show_progress_bar=False)
        return vectors.tolist()

    def embed_query(self, question: str) -> list[float]:
        """One vector for a user question (query prompt, not document prompt)."""
        vector = self._get_model().encode_query(question, show_progress_bar=False)
        return vector.tolist()

    def _get_model(self) -> Any:
        if self._checked:
            return self._model
        with self._lock:
            # Another thread may have finished the load while this one waited.
            if not self._checked:
                self._loading = True
                try:
                    self._load_and_check()
                finally:
                    self._loading = False
        return self._model

    def _load_and_check(self) -> None:
        if self._model is None:
            # Imported here because importing sentence_transformers loads torch,
            # which takes seconds. Importing this module stays fast this way.
            from sentence_transformers import SentenceTransformer

            model_id = self._settings.embedding_model_id
            logger.info("Loading embedding model %s", model_id)
            started = time.perf_counter()
            self._model = SentenceTransformer(model_id, device="cpu")
            logger.info("Embedding model loaded in %.1f s", time.perf_counter() - started)

        dimension = self._model.get_embedding_dimension()
        if dimension != EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                f"Embedding model {self._settings.embedding_model_id} produces "
                f"{dimension}-dimensional vectors, but the database column is "
                f"vector({EMBEDDING_DIMENSIONS}). Use a {EMBEDDING_DIMENSIONS}-"
                "dimensional model or add a migration."
            )
        self._checked = True
