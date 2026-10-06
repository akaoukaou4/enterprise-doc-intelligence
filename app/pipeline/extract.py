"""Stage 1: PDF -> Docling document (structure, pages, headings, tables).

Converting is slow (about 12 s per page on CPU), so this stage only runs Docling
and returns its result. Nothing else happens here.
"""

from functools import lru_cache
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling_core.types.doc import DoclingDocument


@lru_cache(maxsize=1)
def _get_converter() -> DocumentConverter:
    # Created once: building the converter loads models, which is slow.
    return DocumentConverter()


def extract_document(pdf_path: Path) -> DoclingDocument:
    """Convert a PDF file into a structured Docling document."""
    return _get_converter().convert(pdf_path).document
