from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import NotFoundError, register_error_handlers


def build_test_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/missing")
    def missing():
        raise NotFoundError("Document 42 not found")

    @app.get("/boom")
    def boom():
        raise RuntimeError("something internal")

    return app


def test_app_error_returns_structured_json():
    client = TestClient(build_test_app())

    response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Document 42 not found"}}


def test_unhandled_error_returns_generic_500_without_leaking_details():
    client = TestClient(build_test_app(), raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "something internal" not in response.text
