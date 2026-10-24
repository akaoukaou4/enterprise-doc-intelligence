import uuid

import pytest

from app.core.config import Settings
from app.core.errors import ConflictError, ExternalServiceError, NotFoundError
from app.db.models import Document
from app.services.documents import DocumentService


class FakeStorage:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.deleted: list[str] = []
        self.fail_delete = False

    def delete(self, key: str) -> None:
        if self.fail_delete:
            raise ExternalServiceError("Object storage request failed.")
        self.events.append("delete_file")
        self.deleted.append(key)


class FakeSession:
    def __init__(self, events: list[str], existing: Document | None) -> None:
        self.events = events
        self.existing = existing
        self.deleted_rows: list[Document] = []
        self.get_kwargs: dict = {}
        self.rolled_back = False
        self.fail_commit = False

    def get(self, model, document_id, **kwargs):
        self.get_kwargs = kwargs
        return self.existing

    def delete(self, obj: Document) -> None:
        self.deleted_rows.append(obj)

    def commit(self) -> None:
        if self.fail_commit:
            raise RuntimeError("db down")
        self.events.append("commit")

    def rollback(self) -> None:
        self.rolled_back = True


def _document(status: str = "processed") -> Document:
    return Document(
        id=uuid.uuid4(),
        filename="a.pdf",
        storage_key="documents/x/a.pdf",
        status=status,
    )


def _setup(
    existing: Document | None,
) -> tuple[DocumentService, FakeSession, FakeStorage, list[str]]:
    events: list[str] = []
    db = FakeSession(events, existing)
    storage = FakeStorage(events)
    service = DocumentService(Settings(_env_file=None), db, storage)  # type: ignore[arg-type]
    return service, db, storage, events


def test_delete_commits_the_row_before_removing_the_file() -> None:
    document = _document()
    service, db, storage, events = _setup(document)

    service.delete(document.id)

    assert db.deleted_rows == [document]
    assert storage.deleted == ["documents/x/a.pdf"]
    assert events == ["commit", "delete_file"]


def test_delete_locks_the_row() -> None:
    document = _document()
    service, db, _, _ = _setup(document)

    service.delete(document.id)

    assert db.get_kwargs == {"with_for_update": True}


@pytest.mark.parametrize("status", ["uploaded", "processed", "failed"])
def test_delete_is_allowed_in_every_status_except_processing(status: str) -> None:
    document = _document(status)
    service, db, _, _ = _setup(document)

    service.delete(document.id)

    assert db.deleted_rows == [document]


def test_delete_unknown_document_raises_not_found_and_touches_nothing() -> None:
    service, db, storage, _ = _setup(None)

    with pytest.raises(NotFoundError):
        service.delete(uuid.uuid4())

    assert db.deleted_rows == []
    assert storage.deleted == []


def test_delete_while_processing_raises_conflict_and_touches_nothing() -> None:
    document = _document("processing")
    service, db, storage, _ = _setup(document)

    with pytest.raises(ConflictError):
        service.delete(document.id)

    assert db.deleted_rows == []
    assert storage.deleted == []


def test_storage_failure_after_commit_does_not_fail_the_delete() -> None:
    document = _document()
    service, db, storage, _ = _setup(document)
    storage.fail_delete = True

    service.delete(document.id)

    assert db.deleted_rows == [document]


def test_database_failure_rolls_back_and_keeps_the_file() -> None:
    document = _document()
    service, db, storage, _ = _setup(document)
    db.fail_commit = True

    with pytest.raises(RuntimeError):
        service.delete(document.id)

    assert db.rolled_back is True
    assert storage.deleted == []
