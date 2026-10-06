"""The whole pipeline in one call: PDF -> extract -> chunk -> clean.

This is the function that FastAPI (direct mode) and Airflow (orchestrated mode)
will both call later. It does no storage or database work.
"""

from pathlib import Path

from app.pipeline.chunk import chunk_document
from app.pipeline.clean import clean_chunks
from app.pipeline.extract import extract_document
from app.pipeline.models import Chunk


def process_pdf(pdf_path: Path) -> list[Chunk]:
    """Turn a PDF file into clean chunks with page and heading information."""
    document = extract_document(pdf_path)
    return clean_chunks(chunk_document(document))
