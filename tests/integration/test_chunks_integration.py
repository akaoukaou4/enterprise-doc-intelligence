import uuid

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import EMBEDDING_DIMENSIONS, Document, DocumentChunk
from app.pipeline.models import Chunk
from app.services.chunks import ChunkService


def _make_document(db: Session) -> Document:
    document = Document(
        id=uuid.uuid4(),
        filename="chunks-test.pdf",
        storage_key=f"documents/{uuid.uuid4()}/chunks-test.pdf",
        content_type="application/pdf",
        size_bytes=1,
    )
    db.add(document)
    db.commit()
    return document


def _vector(first_value: float) -> list[float]:
    """A valid 768-dimensional vector whose first value we can check later."""
    return [first_value] + [0.0] * (EMBEDDING_DIMENSIONS - 1)


def _read_chunks(engine: Engine, document_id: uuid.UUID) -> list[DocumentChunk]:
    """Read from a separate session, so we see what was really committed."""
    with Session(engine) as other:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(other.scalars(statement))


def test_chunks_are_stored_with_provenance_and_vectors(engine: Engine, db: Session) -> None:
    document = _make_document(db)
    chunks = [
        Chunk(text="first", page_numbers=[2, 3], heading="6.1 Risk"),
        Chunk(text="second", page_numbers=[4], heading=None),
        Chunk(text="third", page_numbers=[5], heading="7 Support"),
    ]
    vectors = [_vector(0.25), _vector(0.5), _vector(0.75)]

    stored = ChunkService(db).replace_chunks(document.id, chunks, vectors)

    assert stored == 3
    rows = _read_chunks(engine, document.id)
    assert [row.chunk_index for row in rows] == [0, 1, 2]
    assert [row.text for row in rows] == ["first", "second", "third"]
    assert [row.page_numbers for row in rows] == [[2, 3], [4], [5]]
    assert [row.heading for row in rows] == ["6.1 Risk", None, "7 Support"]
    assert all(len(row.embedding) == EMBEDDING_DIMENSIONS for row in rows)
    assert [float(row.embedding[0]) for row in rows] == [0.25, 0.5, 0.75]


def test_replacing_chunks_removes_the_old_ones(engine: Engine, db: Session) -> None:
    document = _make_document(db)
    service = ChunkService(db)
    old = [Chunk(text=f"old {i}", page_numbers=[1], heading=None) for i in range(3)]
    service.replace_chunks(document.id, old, [_vector(0.1)] * 3)

    new = [Chunk(text=f"new {i}", page_numbers=[2], heading=None) for i in range(2)]
    stored = service.replace_chunks(document.id, new, [_vector(0.2)] * 2)

    assert stored == 2
    rows = _read_chunks(engine, document.id)
    assert [row.text for row in rows] == ["new 0", "new 1"]


def test_empty_replacement_clears_the_chunks(engine: Engine, db: Session) -> None:
    document = _make_document(db)
    service = ChunkService(db)
    chunk = Chunk(text="x", page_numbers=[1], heading=None)
    service.replace_chunks(document.id, [chunk], [_vector(0.1)])

    stored = service.replace_chunks(document.id, [], [])

    assert stored == 0
    assert _read_chunks(engine, document.id) == []


def test_deleting_a_document_deletes_its_chunks(engine: Engine, db: Session) -> None:
    document = _make_document(db)
    chunk = Chunk(text="x", page_numbers=[1], heading=None)
    ChunkService(db).replace_chunks(document.id, [chunk], [_vector(0.1)])
    assert len(_read_chunks(engine, document.id)) == 1

    db.delete(document)
    db.commit()

    # The database cascade removed the chunks; no code of ours did.
    assert _read_chunks(engine, document.id) == []


def test_rejected_input_keeps_the_old_chunks(engine: Engine, db: Session) -> None:
    document = _make_document(db)
    service = ChunkService(db)
    chunks = [Chunk(text=f"keep {i}", page_numbers=[1], heading=None) for i in range(2)]
    service.replace_chunks(document.id, chunks, [_vector(0.1)] * 2)

    with pytest.raises(ValueError):
        service.replace_chunks(document.id, chunks, [_vector(0.1)])  # one vector missing
    with pytest.raises(ValueError):
        service.replace_chunks(document.id, chunks, [[0.1, 0.2]] * 2)  # wrong size

    assert [row.text for row in _read_chunks(engine, document.id)] == ["keep 0", "keep 1"]


def test_unknown_document_is_rejected(db: Session) -> None:
    chunk = Chunk(text="x", page_numbers=[1], heading=None)

    with pytest.raises(NotFoundError):
        ChunkService(db).replace_chunks(uuid.uuid4(), [chunk], [_vector(0.1)])


def test_failed_commit_rolls_back_and_keeps_the_old_chunks(
    engine: Engine, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _make_document(db)
    service = ChunkService(db)
    old = [Chunk(text=f"old {i}", page_numbers=[1], heading=None) for i in range(2)]
    service.replace_chunks(document.id, old, [_vector(0.1)] * 2)

    def failing_commit() -> None:
        raise RuntimeError("simulated database failure")

    new = [Chunk(text="new", page_numbers=[2], heading=None)]
    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", failing_commit)
        with pytest.raises(RuntimeError):
            service.replace_chunks(document.id, new, [_vector(0.2)])

    # The delete was part of the failed transaction, so the old chunks survived.
    assert [row.text for row in _read_chunks(engine, document.id)] == ["old 0", "old 1"]


def test_chunk_count_is_unique_per_document_and_index(db: Session) -> None:
    """Sanity check on the data: one row per (document, chunk_index)."""
    document = _make_document(db)
    chunks = [Chunk(text=f"c{i}", page_numbers=[1], heading=None) for i in range(3)]
    ChunkService(db).replace_chunks(document.id, chunks, [_vector(0.1)] * 3)

    total = db.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
    )
    distinct = db.scalar(
        select(func.count(func.distinct(DocumentChunk.chunk_index))).where(
            DocumentChunk.document_id == document.id
        )
    )
    assert total == distinct == 3
