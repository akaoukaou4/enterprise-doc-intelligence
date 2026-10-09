import math
import uuid

import pytest

from app.db.models import EMBEDDING_DIMENSIONS, Document, DocumentChunk
from app.services.retrieval import RetrievalService


def _unit(*coords: float) -> list[float]:
    """A normalized 768-dimensional vector with the given leading coordinates."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[: len(coords)] = coords
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector]


class FakeEmbeddings:
    """Returns a fixed query vector and remembers the questions it received."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector
        self.questions: list[str] = []

    def embed_query(self, question: str) -> list[float]:
        self.questions.append(question)
        return self._vector


@pytest.fixture
def seeded(db):
    document_id = uuid.uuid4()
    document = Document(
        id=document_id,
        filename="retrieval-test.pdf",
        storage_key=f"documents/{document_id}/retrieval-test.pdf",
        content_type="application/pdf",
        size_bytes=1,
        status="processed",
    )
    db.add(document)
    db.flush()
    db.add_all(
        [
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                text="chunk A",
                page_numbers=[3],
                heading="Alpha heading",
                embedding=_unit(1),
            ),
            DocumentChunk(
                document_id=document_id,
                chunk_index=1,
                text="chunk B",
                page_numbers=[4, 5],
                heading=None,
                embedding=_unit(1, 1),
            ),
            DocumentChunk(
                document_id=document_id,
                chunk_index=2,
                text="chunk C",
                page_numbers=[6],
                heading="C heading",
                embedding=_unit(0, 0, 1),
            ),
        ]
    )
    db.commit()
    yield document
    db.rollback()
    db.delete(db.get(Document, document_id))
    db.commit()


def test_search_ranks_by_similarity_and_keeps_provenance(db, seeded) -> None:
    service = RetrievalService(db, FakeEmbeddings(_unit(1)))  # type: ignore[arg-type]

    results = service.search("anything", top_k=20)

    first, second = results[0], results[1]
    assert first.text == "chunk A"
    assert first.similarity == pytest.approx(1.0, abs=1e-5)
    assert first.document_id == seeded.id
    assert first.filename == "retrieval-test.pdf"
    assert first.page_numbers == [3]
    assert first.heading == "Alpha heading"

    assert second.text == "chunk B"
    assert second.similarity == pytest.approx(math.sqrt(0.5), abs=1e-5)
    assert second.page_numbers == [4, 5]
    assert second.heading is None

    similarities = [r.similarity for r in results]
    assert similarities == sorted(similarities, reverse=True)


def test_top_k_limits_the_number_of_results(db, seeded) -> None:
    service = RetrievalService(db, FakeEmbeddings(_unit(1)))  # type: ignore[arg-type]

    results = service.search("anything", top_k=2)

    assert [r.text for r in results] == ["chunk A", "chunk B"]


def test_question_is_stripped_before_embedding(db, seeded) -> None:
    fake = FakeEmbeddings(_unit(1))
    service = RetrievalService(db, fake)  # type: ignore[arg-type]

    service.search("  what is the policy?  ", top_k=1)

    assert fake.questions == ["what is the policy?"]
