from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_db
from app.main import create_app


class FakeSession:
    def execute(self, statement):
        return None


class BrokenSession:
    def execute(self, statement):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_health_db_ok_with_working_session():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeSession()
    client = TestClient(app)

    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_db_returns_502_when_database_is_down():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: BrokenSession()
    client = TestClient(app)

    response = client.get("/health/db")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "external_service_error"
    assert "connection refused" not in response.text
