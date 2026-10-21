"""Upload and ingest every PDF in a folder (Phase 7, step 2).

    uv run python -m scripts.ingest_folder                # dry run: shows the plan only
    uv run python -m scripts.ingest_folder --run          # does the work
    uv run python -m scripts.ingest_folder data/corpus --run

A PDF is matched to the database by file name:
- already uploaded and has chunks   -> skipped
- uploaded but has no chunks        -> ingested (not uploaded a second time)
- not in the database               -> uploaded, then ingested
So the script is safe to stop and run again. One failing file does not stop the others.
The outcome of each ingestion is recorded in documents.status (processed or failed).
Nothing is sent to Gemini. Expect about 3 minutes per short PDF on this CPU.
"""

import argparse
import time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.db.session import get_session_factory
from app.pipeline.process import process_pdf
from app.services.chunks import ChunkService
from app.services.document_status import DocumentStatusService, IngestionRunner
from app.services.documents import PDF_CONTENT_TYPE, DocumentService
from app.services.embeddings import EmbeddingService
from app.services.ingestion import FolderAction, IngestionService, decide_folder_action
from app.services.storage import StorageService

DEFAULT_FOLDER = Path("data/corpus")


def find_existing(db: Session, filename: str) -> tuple[Document | None, int]:
    """The document to reuse for this file name and its chunk count.

    Prefers a document that already has chunks; otherwise the newest one.
    """
    documents = (
        db.execute(
            select(Document)
            .where(Document.filename == filename)
            .order_by(Document.created_at.desc())
        )
        .scalars()
        .all()
    )
    best: tuple[Document | None, int] = (None, 0)
    for document in documents:
        count = db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
        )
        if count:
            return document, count
        if best[0] is None:
            best = (document, 0)
    return best


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload and ingest every PDF in a folder.")
    parser.add_argument("folder", nargs="?", type=Path, default=DEFAULT_FOLDER)
    parser.add_argument("--run", action="store_true", help="do the work (default: dry run)")
    args = parser.parse_args()

    pdfs = sorted(args.folder.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDF files in {args.folder}")

    settings = get_settings()
    failures: list[str] = []
    started_all = time.perf_counter()

    with get_session_factory()() as db:
        # 1. Plan: read-only, shows what would happen.
        plan: list[tuple[Path, Document | None, FolderAction]] = []
        for pdf in pdfs:
            document, chunk_count = find_existing(db, pdf.name)
            action = decide_folder_action(
                has_document=document is not None, chunk_count=chunk_count
            )
            plan.append((pdf, document, action))
            print(f"{action:<18} {pdf.name}  ({chunk_count} chunks in database)")

        todo = [item for item in plan if item[2] != "skip"]
        print(f"\n{len(todo)} of {len(plan)} files need work.")
        if not args.run:
            print("Dry run: nothing changed. Add --run to upload and ingest.")
            return

        # 2. Work: services are created once, so the embedding model loads once.
        storage = StorageService(settings)
        documents = DocumentService(settings, db, storage)
        ingestion = IngestionService(
            storage, EmbeddingService(settings), ChunkService(db), process_pdf
        )
        runner = IngestionRunner(ingestion, DocumentStatusService(db))

        for number, (pdf, document, _action) in enumerate(todo, start=1):
            print(f"\n[{number}/{len(todo)}] {pdf.name}", flush=True)
            started = time.perf_counter()
            try:
                if document is None:
                    document = documents.create(pdf.name, PDF_CONTENT_TYPE, pdf.read_bytes())
                    print(f"  uploaded, document id {document.id}")
                result = runner.run(document)
            except Exception as error:  # noqa: BLE001 - one bad file must not stop the batch
                db.rollback()
                failures.append(pdf.name)
                print(f"  FAILED: {type(error).__name__}: {error}")
                continue
            print(
                f"  {result.stored_rows} chunks stored "
                f"(pipeline {result.pipeline_seconds:.0f} s, "
                f"embeddings {result.embedding_seconds:.0f} s, "
                f"total {time.perf_counter() - started:.0f} s)"
            )

    print(f"\nDone in {time.perf_counter() - started_all:.0f} s. Failed: {len(failures)}")
    for name in failures:
        print(f"  - {name}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
