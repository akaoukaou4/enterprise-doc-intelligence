import uuid
from unittest.mock import MagicMock

import pytest

from app.db.models import EMBEDDING_DIMENSIONS
from app.pipeline.models import Chunk
from app.services.chunks import ChunkService


def _chunk(text: str) -> Chunk:
    return Chunk(text=text, page_numbers=[1], heading=None)


def test_different_number_of_chunks_and_vectors_is_rejected() -> None:
    db = MagicMock()
    vectors = [[0.0] * EMBEDDING_DIMENSIONS]

    with pytest.raises(ValueError, match="2 chunks but 1 vectors"):
        ChunkService(db).replace_chunks(uuid.uuid4(), [_chunk("a"), _chunk("b")], vectors)

    # Rejected before anything was deleted or written.
    db.execute.assert_not_called()
    db.commit.assert_not_called()


def test_vector_with_wrong_size_is_rejected() -> None:
    db = MagicMock()

    with pytest.raises(ValueError, match=str(EMBEDDING_DIMENSIONS)):
        ChunkService(db).replace_chunks(uuid.uuid4(), [_chunk("a")], [[0.1, 0.2, 0.3]])

    db.execute.assert_not_called()
    db.commit.assert_not_called()
