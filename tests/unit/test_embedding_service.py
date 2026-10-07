import numpy as np
import pytest

from app.core.config import Settings
from app.db.models import EMBEDDING_DIMENSIONS
from app.pipeline.models import Chunk
from app.services.embeddings import EmbeddingService, build_document_text


class FakeModel:
    """Stands in for SentenceTransformer: no download, no computation."""

    def __init__(self, dimension: int = EMBEDDING_DIMENSIONS) -> None:
        self.dimension = dimension
        self.encode_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def get_embedding_dimension(self) -> int:
        return self.dimension

    def encode(self, texts: list[str], **kwargs: object) -> np.ndarray:
        self.encode_calls.append(list(texts))
        # Row i is filled with the value i, so tests can check the order.
        return np.array([[float(i)] * self.dimension for i in range(len(texts))])

    def encode_query(self, text: str, **kwargs: object) -> np.ndarray:
        self.query_calls.append(text)
        return np.full(self.dimension, 0.5)


def make_service(model: FakeModel) -> EmbeddingService:
    return EmbeddingService(Settings(), model=model)


def test_document_text_uses_heading_as_title() -> None:
    chunk = Chunk(text="Some text", page_numbers=[1], heading="6.1 Risk")
    assert build_document_text(chunk) == "title: 6.1 Risk | text: Some text"


def test_document_text_without_heading_uses_none() -> None:
    chunk = Chunk(text="Some text", page_numbers=[1], heading=None)
    assert build_document_text(chunk) == "title: none | text: Some text"


def test_embed_documents_returns_one_vector_per_chunk_in_order() -> None:
    model = FakeModel()
    chunks = [
        Chunk(text="first", page_numbers=[1], heading="A"),
        Chunk(text="second", page_numbers=[2], heading=None),
        Chunk(text="third", page_numbers=[3], heading="C"),
    ]

    vectors = make_service(model).embed_documents(chunks)

    assert len(vectors) == 3
    assert all(len(vector) == EMBEDDING_DIMENSIONS for vector in vectors)
    assert [vector[0] for vector in vectors] == [0.0, 1.0, 2.0]
    # One batch call, with the formatted document strings.
    assert model.encode_calls == [
        [
            "title: A | text: first",
            "title: none | text: second",
            "title: C | text: third",
        ]
    ]


def test_embed_documents_with_no_chunks_does_not_call_the_model() -> None:
    model = FakeModel()

    assert make_service(model).embed_documents([]) == []
    assert model.encode_calls == []


def test_embed_query_uses_the_query_encoder_with_the_raw_question() -> None:
    model = FakeModel()

    vector = make_service(model).embed_query("What is an incident?")

    assert len(vector) == EMBEDDING_DIMENSIONS
    assert model.query_calls == ["What is an incident?"]
    # The question must not be formatted like a document.
    assert model.encode_calls == []


def test_wrong_model_dimension_is_rejected() -> None:
    service = make_service(FakeModel(dimension=3))

    with pytest.raises(RuntimeError, match=str(EMBEDDING_DIMENSIONS)):
        service.embed_query("anything")
