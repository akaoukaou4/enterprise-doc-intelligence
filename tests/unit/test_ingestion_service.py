from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.ingestion import IngestionService, decide_folder_action


class FakeStorage:
    def __init__(self) -> None:
        self.downloaded: list[str] = []

    def download(self, key: str) -> bytes:
        self.downloaded.append(key)
        return b"%PDF-fake"


class FakeEmbeddings:
    def embed_documents(self, chunks):
        return [[0.0] * 3 for _ in chunks]


class FakeChunks:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def replace_chunks(self, document_id, chunks, vectors) -> int:
        self.calls.append((document_id, list(chunks), vectors))
        return len(chunks)


def make_service(process_pdf):
    storage, chunks = FakeStorage(), FakeChunks()
    service = IngestionService(storage, FakeEmbeddings(), chunks, process_pdf)
    return service, storage, chunks


def test_ingest_runs_the_whole_chain_and_reports_counts() -> None:
    seen: dict = {}

    def process_pdf(path: Path):
        seen["bytes"] = path.read_bytes()  # the temporary copy exists while processing
        return ["chunk one", "chunk two"]

    service, storage, chunks = make_service(process_pdf)
    document = SimpleNamespace(id="doc-1", storage_key="documents/doc-1/a.pdf")

    result = service.ingest(document)

    assert storage.downloaded == ["documents/doc-1/a.pdf"]
    assert seen["bytes"] == b"%PDF-fake"
    assert chunks.calls[0][0] == "doc-1"
    assert chunks.calls[0][1] == ["chunk one", "chunk two"]
    assert len(chunks.calls[0][2]) == 2
    assert (result.chunk_count, result.stored_rows) == (2, 2)


def test_ingest_stores_nothing_when_the_pipeline_fails() -> None:
    def process_pdf(path: Path):
        raise RuntimeError("conversion failed")

    service, _, chunks = make_service(process_pdf)
    document = SimpleNamespace(id="doc-1", storage_key="k")

    with pytest.raises(RuntimeError):
        service.ingest(document)
    assert chunks.calls == []


@pytest.mark.parametrize(
    ("has_document", "chunk_count", "expected"),
    [
        (True, 21, "skip"),
        (True, 0, "ingest"),
        (False, 0, "upload_and_ingest"),
    ],
)
def test_decide_folder_action(has_document: bool, chunk_count: int, expected: str) -> None:
    assert decide_folder_action(has_document=has_document, chunk_count=chunk_count) == expected
