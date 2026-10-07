"""Stage 2: Docling document -> list of Chunk objects.

Uses Docling's HybridChunker and keeps the provenance we need for citations
(page numbers and the nearest heading). Chunks that come from the table of
contents are dropped here, because that decision needs Docling's label for the
table ("document_index"), not a text pattern.

Chunk size is measured with the EmbeddingGemma tokenizer, so the token budget
refers to the same model that later embeds the chunks.
"""

from functools import lru_cache
from typing import Any

from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.types.doc import DoclingDocument
from transformers import AutoTokenizer

from app.core.config import get_settings
from app.pipeline.models import Chunk

TOC_LABEL = "document_index"

# The model accepts up to 2048 tokens. We keep 512 on purpose: it is the same
# budget the chunks had in Phase 3, so only the tokenizer changes. Chunk size
# is tuned later, with evaluation data (Phase 7), not by intuition.
MAX_CHUNK_TOKENS = 512


@lru_cache(maxsize=1)
def get_tokenizer() -> HuggingFaceTokenizer:
    """The tokenizer of the embedding model, loaded once (reads the HF cache)."""
    return HuggingFaceTokenizer(
        tokenizer=AutoTokenizer.from_pretrained(get_settings().embedding_model_id),
        max_tokens=MAX_CHUNK_TOKENS,
    )


@lru_cache(maxsize=1)
def get_default_chunker() -> HybridChunker:
    """HybridChunker that measures chunk size with the embedding model's tokenizer."""
    return HybridChunker(tokenizer=get_tokenizer())


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
    HybridChunker with the embedding model's tokenizer.
    """
    chunker = chunker or get_default_chunker()
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
