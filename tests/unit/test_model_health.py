import pytest
from fastapi.testclient import TestClient

from app import main
from app.api.deps import get_embedding_service
from app.main import create_app


class FakeEmbeddings:
    def __init__(self, state: str) -> None:
        self.state = state


def _client(state: str) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddings(state)
    return TestClient(app)


@pytest.mark.parametrize(
    ("state", "status_code"),
    [("ready", 200), ("loading", 503), ("idle", 503)],
)
def test_model_health_maps_the_state_to_the_status_code(state: str, status_code: int) -> None:
    response = _client(state).get("/health/model")

    assert response.status_code == status_code
    assert response.json() == {"status": state}


class _LoadRecorder:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls = 0
        self._error = error

    def load(self) -> None:
        self.calls += 1
        if self._error:
            raise self._error


def test_preload_loads_the_model_once(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _LoadRecorder()
    monkeypatch.setattr(main, "get_embedding_service", lambda: recorder)

    main._preload_embedding_model()

    assert recorder.calls == 1


def test_a_failed_preload_does_not_crash_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _LoadRecorder(RuntimeError("no token"))
    monkeypatch.setattr(main, "get_embedding_service", lambda: recorder)

    main._preload_embedding_model()  # must not raise

    assert recorder.calls == 1
