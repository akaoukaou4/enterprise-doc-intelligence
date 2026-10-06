from types import SimpleNamespace

from app.pipeline.chunk import chunk_document
from app.pipeline.models import Chunk


def make_item(label: str, pages: list[int]) -> SimpleNamespace:
    return SimpleNamespace(
        label=SimpleNamespace(value=label),
        prov=[SimpleNamespace(page_no=p) for p in pages],
    )


def make_chunk(text: str, headings: list[str] | None, items: list[SimpleNamespace]):
    return SimpleNamespace(text=text, meta=SimpleNamespace(headings=headings, doc_items=items))


class FakeChunker:
    def __init__(self, chunks):
        self._chunks = chunks

    def chunk(self, dl_doc):
        return iter(self._chunks)


def run(chunks):
    return chunk_document(doc=None, chunker=FakeChunker(chunks))


def test_converts_text_pages_and_heading():
    raw = make_chunk("Hello", ["5.2 Policy"], [make_item("text", [9])])
    assert run([raw]) == [Chunk(text="Hello", page_numbers=[9], heading="5.2 Policy")]


def test_chunk_spanning_pages_gets_sorted_unique_pages():
    items = [make_item("text", [3, 2]), make_item("text", [3])]
    result = run([make_chunk("x", ["A"], items)])
    assert result[0].page_numbers == [2, 3]


def test_table_of_contents_chunks_are_dropped():
    toc = make_chunk("Foreword......... iv", ["Contents"], [make_item("document_index", [3])])
    real = make_chunk("Scope text", ["1 Scope"], [make_item("text", [7])])
    result = run([toc, real])
    assert [c.text for c in result] == ["Scope text"]


def test_regular_table_is_kept():
    table = make_chunk("A, 1 = B", ["Annex A"], [make_item("table", [17])])
    assert len(run([table])) == 1


def test_nearest_heading_is_the_last_one():
    result = run([make_chunk("x", ["3 Pipeline", "3.1 Backends"], [make_item("text", [2])])])
    assert result[0].heading == "3.1 Backends"


def test_missing_headings_become_none():
    assert run([make_chunk("x", None, [make_item("text", [1])])])[0].heading is None
    assert run([make_chunk("x", [], [make_item("text", [1])])])[0].heading is None
