import importlib.util
from pathlib import Path

import pytest
import requests

_PATH = Path(__file__).resolve().parents[2] / "ui" / "api_client.py"
_SPEC = importlib.util.spec_from_file_location("ui_api_client", _PATH)
module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(module)


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: object = None) -> None:
        self.status_code = status_code
        self._payload = payload

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> object:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[tuple] = []

    def request(self, method, url, timeout, **kwargs):
        self.calls.append((method, url, timeout, kwargs))
        if self.error:
            raise self.error
        return self.response


def _client(session: FakeSession, base_url: str = "http://api.test") -> "module.ApiClient":
    return module.ApiClient(base_url, session)


def test_list_documents_sends_paging_and_returns_json() -> None:
    session = FakeSession(FakeResponse(200, {"items": [], "total": 0, "limit": 5, "offset": 10}))

    page = _client(session, "http://api.test/").list_documents(limit=5, offset=10)

    method, url, _timeout, kwargs = session.calls[0]
    assert (method, url) == ("GET", "http://api.test/api/v1/documents")
    assert kwargs["params"] == {"limit": 5, "offset": 10}
    assert page["total"] == 0


def test_upload_sends_the_file_as_multipart_pdf() -> None:
    session = FakeSession(FakeResponse(201, {"id": "x", "filename": "a.pdf"}))

    document = _client(session).upload_document("a.pdf", b"%PDF-1")

    method, url, _timeout, kwargs = session.calls[0]
    assert (method, url) == ("POST", "http://api.test/api/v1/documents")
    assert kwargs["files"]["file"] == ("a.pdf", b"%PDF-1", "application/pdf")
    assert document["filename"] == "a.pdf"


def test_ask_omits_top_k_when_not_given() -> None:
    session = FakeSession(FakeResponse(200, {"answer": "x", "found": True, "citations": []}))

    _client(session).ask("How many days?")

    assert session.calls[0][3]["json"] == {"question": "How many days?"}


def test_ask_sends_top_k_when_given() -> None:
    session = FakeSession(FakeResponse(200, {"answer": "x", "found": True, "citations": []}))

    _client(session).ask("How many days?", top_k=3)

    assert session.calls[0][3]["json"] == {"question": "How many days?", "top_k": 3}


def test_api_error_message_is_passed_through() -> None:
    payload = {"error": {"code": "validation_failed", "message": "Only PDF files are accepted."}}
    session = FakeSession(FakeResponse(422, payload))

    with pytest.raises(module.ApiError, match="Only PDF files are accepted."):
        _client(session).upload_document("a.txt", b"x")


def test_error_without_json_gives_a_generic_message_with_the_status() -> None:
    session = FakeSession(FakeResponse(502, None))

    with pytest.raises(module.ApiError, match="502"):
        _client(session).ask("q")


def test_unreachable_api_gives_a_clear_message() -> None:
    session = FakeSession(error=requests.ConnectionError())

    with pytest.raises(module.ApiError, match="Cannot reach the API"):
        _client(session).list_documents()


def test_timeout_gives_a_clear_message() -> None:
    session = FakeSession(error=requests.Timeout())

    with pytest.raises(module.ApiError, match="too long"):
        _client(session).ask("q")


def test_base_url_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_URL", "http://env.test")
    session = FakeSession(FakeResponse(200, {"items": []}))

    module.ApiClient(session=session).list_documents()

    assert session.calls[0][1] == "http://env.test/api/v1/documents"
