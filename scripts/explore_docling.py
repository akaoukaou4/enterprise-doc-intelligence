"""Exploration script: see what Docling produces for one PDF.

This is NOT pipeline code. It is a throwaway tool to look at Docling's output
before designing the chunk schema (Phase 3).

Run from the project root:
    uv run python scripts/explore_docling.py
    uv run python scripts/explore_docling.py path/to/other.pdf
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter

DEFAULT_PDF = Path("data/sample_docs/docling_technical_report.pdf")
OUTPUT_DIR = Path("data/sample_docs/output")
CHUNKS_TO_SHOW = 5


def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Convert the PDF into a structured DoclingDocument.
    print(f"Converting {pdf_path} (first run downloads models, be patient)...")
    start = time.perf_counter()
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    doc = result.document
    print(f"Conversion done in {time.perf_counter() - start:.1f} s\n")

    # 2. Save the full result so we can inspect it by eye.
    (OUTPUT_DIR / f"{pdf_path.stem}.md").write_text(doc.export_to_markdown(), encoding="utf-8")
    (OUTPUT_DIR / f"{pdf_path.stem}.json").write_text(
        json.dumps(doc.export_to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved Markdown and JSON to {OUTPUT_DIR}\n")

    # 3. Overview.
    print("=== OVERVIEW ===")
    print(f"Pages:    {len(doc.pages)}")
    print(f"Texts:    {len(doc.texts)}")
    print(f"Tables:   {len(doc.tables)}")
    print(f"Pictures: {len(doc.pictures)}")

    label_counts = Counter(str(item.label) for item in doc.texts)
    print("\nText item labels:")
    for label, count in label_counts.most_common():
        print(f"  {label}: {count}")

    # 4. Headings with level and page.
    print("\n=== HEADINGS (level, page, text) ===")
    for item in doc.texts:
        if str(item.label).endswith("section_header"):
            page = item.prov[0].page_no if item.prov else "?"
            level = getattr(item, "level", "?")
            print(f"  L{level} p{page}: {item.text[:80]}")

    # 5. Chunks produced by HybridChunker.
    print(f"\n=== FIRST {CHUNKS_TO_SHOW} CHUNKS ===")
    chunker = HybridChunker()
    chunks = list(chunker.chunk(dl_doc=doc))
    print(f"Total chunks: {len(chunks)}\n")

    for i, chunk in enumerate(chunks[:CHUNKS_TO_SHOW]):
        pages = sorted({prov.page_no for item in chunk.meta.doc_items for prov in item.prov})
        print(f"--- chunk {i} ---")
        print(f"pages:    {pages}")
        print(f"headings: {chunk.meta.headings}")
        print(f"chars:    {len(chunk.text)}")
        print(f"text:     {chunk.text[:200]!r}")
        print()


if __name__ == "__main__":
    main()
