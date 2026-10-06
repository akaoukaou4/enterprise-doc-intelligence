"""Check script: run the full pipeline (extract -> chunk -> clean) on one PDF.

Not pipeline code. This runs the real Docling conversion, so it takes minutes.
Run from the project root:
    uv run python -m scripts.run_pipeline "data/sample_docs/Docling Technical Report.pdf"
"""

import sys
import time
from pathlib import Path

from app.pipeline.process import process_pdf

DEFAULT_PDF = Path("data/sample_docs/Docling Technical Report.pdf")


def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF
    start = time.perf_counter()
    chunks = process_pdf(pdf_path)
    elapsed = time.perf_counter() - start

    print(f"{len(chunks)} chunks in {elapsed:.0f} s")
    pages = sorted({p for c in chunks for p in c.page_numbers})
    print(f"Pages covered: {pages}")
    print("\nFirst 5 chunks:")
    for i, c in enumerate(chunks[:5]):
        print(f"  [{i}] pages={c.page_numbers} heading={c.heading!r} | {c.text[:60]!r}")


if __name__ == "__main__":
    main()
