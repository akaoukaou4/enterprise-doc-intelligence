"""Stage 2: Docling document -> list of Chunk objects.

Uses Docling's HybridChunker and keeps the provenance we need for citations
(page numbers and the nearest heading). Chunks that come from the table of
contents are dropped here, because that decision needs Docling's label for the
table ("document_index"), not a text pattern.
"""

from typing import Any

from docling.chunking import HybridChunker
from docling_core.types.doc import DoclingDocument

from app.pipeline.models import Chunk

TOC_LABEL = "document_index"


def _label_value(item: Any) -> str:
    label = item.label
    return str(getattr(label, "value", label))


def _is_table_of_contents(doc_items: list[Any]) -> bool:
    return any(_label_value(item) == TOC_LABEL for item in doc_items)


def _page_numbers(doc_items: list[Any]) -> list[int]:
    return sorted({prov.page_no for item in doc_items for prov in item.prov})


def _nearest_heading(headings: list[str] | None) -> str | None:
    # Docling reports every heading as level 1, so there is no reliable
    # hierarchy. We keep the last (nearest) heading as the section label.
    return headings[-1] if headings else None


def chunk_document(doc: DoclingDocument, chunker: Any | None = None) -> list[Chunk]:
    """Split a Docling document into chunks, skipping table-of-contents chunks.

    The chunker can be passed in (tests use a fake one). By default it is
    HybridChunker with its default tokenizer; Phase 4 switches it to the
    EmbeddingGemma tokenizer.
    """
    chunker = chunker or HybridChunker()
    chunks: list[Chunk] = []
    for raw in chunker.chunk(dl_doc=doc):
        doc_items = raw.meta.doc_items
        if _is_table_of_contents(doc_items):
            continue
        chunks.append(
            Chunk(
                text=raw.text,
                page_numbers=_page_numbers(doc_items),
                heading=_nearest_heading(raw.meta.headings),
            )
        )
    return chunks
