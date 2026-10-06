from app.pipeline.clean import clean_chunks, clean_heading, clean_text
from app.pipeline.models import Chunk

# The license watermark found in the ISO 27001 PDF.
WATERMARK = "--``,,,,,``````,,,,,`,`,`,`,,`,-`-`,,`,,`,`,,`---"


def test_removes_watermark_line_at_start():
    # Chunk 96 of the ISO PDF.
    text = f"{WATERMARK}\nThe organization shall determine external and internal issues."
    assert clean_text(text) == "The organization shall determine external and internal issues."


def test_removes_backspace_and_bom():
    assert clean_text("Con\x08tents\ufeff") == "Contents"


def test_chunk_that_starts_with_watermark_and_bom():
    # Chunk 124 of the ISO PDF.
    text = f"{WATERMARK}\n\ufeff\n- 2) the requirements of this document;\n- b) is effective."
    assert clean_text(text) == "- 2) the requirements of this document;\n- b) is effective."


def test_watermark_only_becomes_empty():
    assert clean_text(WATERMARK) == ""


def test_removes_watermark_in_the_middle():
    assert clean_text(f"Intro\n{WATERMARK}\nNext") == "Intro\nNext"


def test_plain_text_is_unchanged():
    text = "Top management shall establish an information security policy."
    assert clean_text(text) == text


def test_long_dash_line_is_not_a_watermark():
    text = "-" * 30 + "\nA normal line"
    assert clean_text(text) == text


def test_copyright_page_junk_is_removed():
    # Chunk 2 of the ISO PDF.
    text = f"Published in Switzerland\n\x08\n\x08\ufeff\n{WATERMARK}"
    assert clean_text(text) == "Published in Switzerland"


def test_heading_strips_backspace():
    assert clean_heading("Contents\x08") == "Contents"


def test_heading_none_stays_none():
    assert clean_heading(None) is None


def test_heading_that_is_only_junk_becomes_none():
    assert clean_heading("\x08") is None


def test_clean_chunks_drops_empty_and_cleans_the_rest():
    chunks = [
        Chunk(text=WATERMARK, page_numbers=[7], heading="4.1 Context"),
        Chunk(text="Real text\x08", page_numbers=[3], heading="Contents\x08"),
        Chunk(text="Plain text", page_numbers=[4], heading=None),
    ]
    result = clean_chunks(chunks)
    assert len(result) == 2
    assert result[0] == Chunk(text="Real text", page_numbers=[3], heading="Contents")
    assert result[1] == Chunk(text="Plain text", page_numbers=[4], heading=None)


def test_clean_chunks_keeps_order_and_pages():
    chunks = [
        Chunk(text="first", page_numbers=[1, 2], heading="A"),
        Chunk(text="second", page_numbers=[2], heading="B"),
    ]
    result = clean_chunks(chunks)
    assert [c.text for c in result] == ["first", "second"]
    assert result[0].page_numbers == [1, 2]
