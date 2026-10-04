from fastapi.testclient import TestClient

from app.main import create_app


def test_openapi_schema_builds():
    app = create_app()

    schema = app.openapi()

    assert "/health" in schema["paths"]


def test_unknown_api_route_returns_error_shape():
    client = TestClient(create_app())

    response = client.get("/api/v1/nothing-here")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
