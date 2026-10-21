import uuid
from types import SimpleNamespace

import pytest

from app.services.document_status import IngestionRunner


class FakeStatuses:
    def __init__(self, events, fail_on_failed=False):
        self.events = events
        self.fail_on_failed = fail_on_failed

    def mark_processing(self, document_id):
        self.events.append(("processing", document_id))

    def mark_processed(self, document_id):
        self.events.append(("processed", document_id))

    def mark_failed(self, document_id):
        if self.fail_on_failed:
            raise OSError("database down")
        self.events.append(("failed", document_id))


class FakeIngestion:
    def __init__(self, events, error=None):
        self.events = events
        self.error = error

    def ingest(self, document):
        self.events.append(("ingest", document.id))
        if self.error:
            raise self.error
        return "the result"


def _document():
    return SimpleNamespace(id=uuid.uuid4())


def test_success_marks_processing_then_processed():
    events = []
    document = _document()
    runner = IngestionRunner(FakeIngestion(events), FakeStatuses(events))

    assert runner.run(document) == "the result"

    assert events == [
        ("processing", document.id),
        ("ingest", document.id),
        ("processed", document.id),
    ]


def test_failure_marks_failed_and_reraises():
    events = []
    document = _document()
    runner = IngestionRunner(FakeIngestion(events, RuntimeError("boom")), FakeStatuses(events))

    with pytest.raises(RuntimeError, match="boom"):
        runner.run(document)

    assert events == [
        ("processing", document.id),
        ("ingest", document.id),
        ("failed", document.id),
    ]


def test_failure_to_record_failure_does_not_hide_the_original_error():
    events = []
    runner = IngestionRunner(
        FakeIngestion(events, RuntimeError("boom")), FakeStatuses(events, fail_on_failed=True)
    )

    with pytest.raises(RuntimeError, match="boom"):
        runner.run(_document())
