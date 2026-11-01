import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import RequestIdFilter, request_id_var
from app.core.middleware import RequestLogMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestLogMiddleware)

    @app.get("/ping")
    def ping() -> dict:
        return {"ok": True}

    @app.get("/health/x")
    def health() -> dict:
        return {"ok": True}

    @app.get("/boom")
    def boom() -> dict:
        raise RuntimeError("internal detail")

    return TestClient(app, raise_server_exceptions=False)


def test_request_logs_one_line_and_returns_an_id(caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.request")
    response = _client().get("/ping")

    assert response.status_code == 200
    assert len(response.headers["x-request-id"]) == 12
    messages = [r.getMessage() for r in caplog.records if r.name == "app.request"]
    assert len(messages) == 1
    assert messages[0].startswith("GET /ping -> 200 in ")
    assert messages[0].endswith(" ms")


def test_query_string_is_never_logged(caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.request")
    _client().get("/ping?question=secretword")

    messages = [r.getMessage() for r in caplog.records if r.name == "app.request"]
    assert len(messages) == 1
    assert "secretword" not in messages[0]


def test_client_supplied_id_is_ignored() -> None:
    response = _client().get("/ping", headers={"X-Request-ID": "evil\ninjected"})

    assert response.headers["x-request-id"] != "evil\ninjected"


def test_unexpected_error_is_logged_as_500(caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.request")
    response = _client().get("/boom")

    assert response.status_code == 500
    messages = [r.getMessage() for r in caplog.records if r.name == "app.request"]
    assert messages[0].startswith("GET /boom -> 500 in ")


def test_health_requests_are_not_logged_at_info(caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.request")
    _client().get("/health/x")

    assert [r for r in caplog.records if r.name == "app.request"] == []


def test_filter_puts_the_request_id_on_records() -> None:
    record = logging.LogRecord("x", logging.INFO, "f", 1, "m", None, None)
    request_id_var.set("abc123")
    RequestIdFilter().filter(record)

    assert record.request_id == "abc123"
