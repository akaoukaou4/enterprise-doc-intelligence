import pytest

from app.core.errors import ValidationFailedError
from app.services.retrieval import MAX_QUESTION_CHARS, MAX_TOP_K, RetrievalService


def _service() -> RetrievalService:
    # Validation happens before the database or the model is used.
    return RetrievalService(db=None, embeddings=None)  # type: ignore[arg-type]


@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_empty_question_is_rejected(question: str) -> None:
    with pytest.raises(ValidationFailedError):
        _service().search(question)


def test_too_long_question_is_rejected() -> None:
    with pytest.raises(ValidationFailedError):
        _service().search("x" * (MAX_QUESTION_CHARS + 1))


@pytest.mark.parametrize("top_k", [0, -1, MAX_TOP_K + 1])
def test_top_k_out_of_range_is_rejected(top_k: int) -> None:
    with pytest.raises(ValidationFailedError):
        _service().search("a valid question", top_k=top_k)
