"""Cleaning rules for chunks, each one backed by what we saw in real PDFs.

Pure functions: text in, text out. No Docling, no I/O.

Rules (from the exploration of the ISO 27001 PDF):
1. Remove invisible characters (backspace \\x08 and byte-order mark \\ufeff).
2. Remove the license watermark line (a line made of backticks, commas, hyphens).
3. Drop chunks that are empty after cleaning.

Dropping the table of contents is done in chunk.py, because it needs the
Docling label of the table, not a text pattern.
"""

import re
from dataclasses import replace

from app.pipeline.models import Chunk

_INVISIBLE_CHARS = re.compile(r"[\x08\ufeff]")

# Starts with "--", contains at least one backtick, and is 15+ characters of
# backticks, commas and hyphens. The backtick requirement prevents removing an
# ordinary line of dashes. The whole line (and its newline) is removed.
_WATERMARK_LINE = re.compile(r"[ \t]*--(?=[,-]*`)[`,-]{15,}[ \t]*\n?")

_EXTRA_NEWLINES = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Remove invisible characters and watermark lines, and tidy the whitespace."""
    text = _INVISIBLE_CHARS.sub("", text)
    text = _WATERMARK_LINE.sub("", text)
    text = _EXTRA_NEWLINES.sub("\n\n", text)
    return text.strip()


def clean_heading(heading: str | None) -> str | None:
    """Clean a heading. A heading that is only junk becomes None."""
    if heading is None:
        return None
    cleaned = clean_text(heading)
    return cleaned or None


def clean_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Clean every chunk and drop the ones that are empty afterwards."""
    result: list[Chunk] = []
    for chunk in chunks:
        text = clean_text(chunk.text)
        if not text:
            continue
        result.append(replace(chunk, text=text, heading=clean_heading(chunk.heading)))
    return result
