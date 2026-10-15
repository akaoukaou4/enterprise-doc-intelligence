"""Ingestion of one stored document: storage -> pipeline -> embeddings -> chunks.

This is the chain that `scripts/ingest_document.py` ran inline in Phase 4. It lives
here so the single-document script, the bulk script and (Phase 8) Airflow call the
same code. The pipeline function is injected, so this module imports no Docling
and unit tests need no model.
"""

import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.db.models import Document
    from app.services.chunks import ChunkService
    from app.services.embeddings import EmbeddingService
    from app.services.storage import StorageService

# What a folder script does with one PDF, given what the database already holds.
FolderAction = Literal["skip", "ingest", "upload_and_ingest"]


def decide_folder_action(*, has_document: bool, chunk_count: int) -> FolderAction:
    """Decide the next step for one PDF so that re-running a folder script is safe."""
    if has_document and chunk_count > 0:
        return "skip"  # already uploaded and ingested
    if has_document:
        return "ingest"  # uploaded earlier, ingestion never finished: do not upload twice
    return "upload_and_ingest"


@dataclass(frozen=True)
class IngestionResult:
    chunk_count: int
    stored_rows: int
    pipeline_seconds: float
    embedding_seconds: float


class IngestionService:
    def __init__(
        self,
        storage: "StorageService",
        embeddings: "EmbeddingService",
        chunks: "ChunkService",
        process_pdf: Callable[[Path], Sequence],
    ) -> None:
        self._storage = storage
        self._embeddings = embeddings
        self._chunks = chunks
        self._process_pdf = process_pdf

    def ingest(self, document: "Document") -> IngestionResult:
        """Process one uploaded document and replace its stored chunks."""
        # 1. The original PDF comes back from object storage.
        data = self._storage.download(document.storage_key)

        # 2. The pipeline works on a file path, so write a temporary copy.
        with tempfile.TemporaryDirectory() as folder:
            pdf_path = Path(folder) / "document.pdf"
            pdf_path.write_bytes(data)
            started = time.perf_counter()
            chunks = self._process_pdf(pdf_path)
            pipeline_seconds = time.perf_counter() - started

        # 3. One vector per chunk.
        started = time.perf_counter()
        vectors = self._embeddings.embed_documents(chunks)
        embedding_seconds = time.perf_counter() - started

        # 4. Chunks, provenance and vectors go to PostgreSQL in one transaction.
        stored = self._chunks.replace_chunks(document.id, chunks, vectors)
        return IngestionResult(len(chunks), stored, pipeline_seconds, embedding_seconds)
