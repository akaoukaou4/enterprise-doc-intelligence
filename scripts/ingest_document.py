"""Direct ingestion of one uploaded document (Phase 4, no Airflow).

Runs the whole chain for a document that is already uploaded:
MinIO -> pipeline (Docling, chunks) -> embeddings -> PostgreSQL (pgvector).

    uv run python -m scripts.ingest_document <document_id>

Running it again replaces the document's chunks, so it is safe to repeat.
Airflow tasks will later call the same functions.
"""

import argparse
import tempfile
import time
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.db.models import Document
from app.db.session import get_session_factory
from app.pipeline.process import process_pdf
from app.services.chunks import ChunkService
from app.services.embeddings import EmbeddingService
from app.services.storage import StorageService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest one uploaded document.")
    parser.add_argument("document_id", type=uuid.UUID, help="id returned by the upload")
    args = parser.parse_args()

    settings = get_settings()
    storage = StorageService(settings)
    embeddings = EmbeddingService(settings)

    with get_session_factory()() as db:
        document = db.get(Document, args.document_id)
        if document is None:
            raise SystemExit(f"Document not found: {args.document_id}")
        print(f"Document: {document.filename} ({document.size_bytes} bytes)")

        # 1. The original PDF comes back from object storage.
        data = storage.download(document.storage_key)

        # 2. The pipeline works on a file path, so write a temporary copy.
        with tempfile.TemporaryDirectory() as folder:
            pdf_path = Path(folder) / "document.pdf"
            pdf_path.write_bytes(data)
            started = time.perf_counter()
            chunks = process_pdf(pdf_path)
        print(f"1. Pipeline:   {len(chunks)} chunks in {time.perf_counter() - started:.0f} s")

        # 3. One vector per chunk.
        started = time.perf_counter()
        vectors = embeddings.embed_documents(chunks)
        print(f"2. Embeddings: {len(vectors)} vectors in {time.perf_counter() - started:.0f} s")

        # 4. Chunks, provenance and vectors go to PostgreSQL in one transaction.
        stored = ChunkService(db).replace_chunks(document.id, chunks, vectors)
        print(f"3. Stored:     {stored} rows in document_chunks")


if __name__ == "__main__":
    main()
