import pytest

from app.core.errors import ValidationFailedError
from app.services.documents import MAX_LIST_LIMIT, DocumentService


def _service() -> DocumentService:
    # Paging is validated before any database access, so no real session is needed.
    return DocumentService(None, None, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (MAX_LIST_LIMIT + 1, 0), (10, -1)],
)
def test_list_documents_refuses_bad_paging(limit: int, offset: int) -> None:
    with pytest.raises(ValidationFailedError):
        _service().list_documents(limit, offset)
