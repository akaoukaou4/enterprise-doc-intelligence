"""Direct ingestion of one uploaded document (Phase 4, no Airflow).

Runs the whole chain for a document that is already uploaded:
MinIO -> pipeline (Docling, chunks) -> embeddings -> PostgreSQL (pgvector).

    uv run python -m scripts.ingest_document <document_id>

Running it again replaces the document's chunks, so it is safe to repeat.
The chain itself lives in app/services/ingestion.py (shared with ingest_folder).
"""

import argparse
import uuid

from app.core.config import get_settings
from app.db.models import Document
from app.db.session import get_session_factory
from app.pipeline.process import process_pdf
from app.services.chunks import ChunkService
from app.services.embeddings import EmbeddingService
from app.services.ingestion import IngestionService
from app.services.storage import StorageService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest one uploaded document.")
    parser.add_argument("document_id", type=uuid.UUID, help="id returned by the upload")
    args = parser.parse_args()

    settings = get_settings()

    with get_session_factory()() as db:
        document = db.get(Document, args.document_id)
        if document is None:
            raise SystemExit(f"Document not found: {args.document_id}")
        print(f"Document: {document.filename} ({document.size_bytes} bytes)")

        service = IngestionService(
            StorageService(settings), EmbeddingService(settings), ChunkService(db), process_pdf
        )
        result = service.ingest(document)

    print(f"1. Pipeline:   {result.chunk_count} chunks in {result.pipeline_seconds:.0f} s")
    print(f"2. Embeddings: {result.chunk_count} vectors in {result.embedding_seconds:.0f} s")
    print(f"3. Stored:     {result.stored_rows} rows in document_chunks")


if __name__ == "__main__":
    main()
