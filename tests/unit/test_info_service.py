from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.info import InfoService


def test_info_service_builds_response_from_settings():
    settings = Settings(app_name="Test App", app_version="9.9.9", app_env="test")

    result = InfoService(settings).get_info()

    assert result.name == "Test App"
    assert result.version == "9.9.9"
    assert result.environment == "test"


def test_info_endpoint_returns_200():
    client = TestClient(create_app())

    response = client.get("/api/v1/info")

    assert response.status_code == 200
    assert {"name", "version", "environment"} <= response.json().keys()
