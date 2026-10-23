import sys
import threading
import time
import types

import pytest

from app.core.config import Settings
from app.db.models import EMBEDDING_DIMENSIONS
from app.services.embeddings import EmbeddingService


class _Vector:
    def tolist(self) -> list[float]:
        return [0.0]


class _InjectedModel:
    def get_embedding_dimension(self) -> int:
        return EMBEDDING_DIMENSIONS

    def encode_query(self, question: str, show_progress_bar: bool = False) -> _Vector:
        return _Vector()


def _install_fake_sentence_transformers(monkeypatch, model_class) -> None:
    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = model_class
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)


def test_state_goes_from_idle_to_ready_on_first_use() -> None:
    service = EmbeddingService(Settings(), model=_InjectedModel())
    assert service.state == "idle"

    service.embed_query("a question")

    assert service.state == "ready"


def test_concurrent_loads_construct_the_model_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[str] = []
    states_during_load: list[str] = []
    holder: list[EmbeddingService] = []

    class FakeModel:
        def __init__(self, model_id: str, device: str) -> None:
            created.append(model_id)
            states_during_load.append(holder[0].state)
            time.sleep(0.2)  # long enough for the other threads to arrive

        def get_embedding_dimension(self) -> int:
            return EMBEDDING_DIMENSIONS

    _install_fake_sentence_transformers(monkeypatch, FakeModel)
    service = EmbeddingService(Settings())
    holder.append(service)

    threads = [threading.Thread(target=service.load) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(created) == 1
    assert states_during_load == ["loading"]
    assert service.state == "ready"


def test_a_failed_load_goes_back_to_idle_and_the_next_call_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[int] = []

    class FlakyModel:
        def __init__(self, model_id: str, device: str) -> None:
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("download failed")

        def get_embedding_dimension(self) -> int:
            return EMBEDDING_DIMENSIONS

    _install_fake_sentence_transformers(monkeypatch, FlakyModel)
    service = EmbeddingService(Settings())

    with pytest.raises(RuntimeError, match="download failed"):
        service.load()
    assert service.state == "idle"

    service.load()
    assert service.state == "ready"
    assert len(attempts) == 2
