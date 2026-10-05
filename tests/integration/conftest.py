import socket
from collections.abc import Iterator
from urllib.parse import urlparse

import pytest
from sqlalchemy import Engine, create_engine, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Document
from app.services.storage import StorageService

# Integration tests need the real Postgres and MinIO from docker-compose.
# When they are not configured or not reachable (e.g. in CI), tests are skipped.


def _reachable(url: str) -> bool:
    parsed = urlparse(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((parsed.hostname, port), timeout=2):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def settings() -> Settings:
    config = Settings()
    if not config.database_url:
        pytest.skip("DATABASE_URL is not set")
    if not config.minio_endpoint:
        pytest.skip("MINIO_ENDPOINT is not set")
    return config


@pytest.fixture(scope="session")
def engine(settings: Settings) -> Iterator[Engine]:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        engine.dispose()
        pytest.skip("PostgreSQL is not reachable")

    if not inspect(engine).has_table("documents"):
        engine.dispose()
        pytest.fail("Table 'documents' is missing. Run: uv run alembic upgrade head")

    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def storage(settings: Settings) -> StorageService:
    if not _reachable(settings.minio_endpoint):
        pytest.skip("MinIO is not reachable")
    return StorageService(settings)


@pytest.fixture
def db(engine: Engine, storage: StorageService) -> Iterator[Session]:
    """A real session. Removes whatever the test created, and nothing else."""
    session = Session(engine, autoflush=False, expire_on_commit=False)
    existing_ids = set(session.scalars(select(Document.id)))

    yield session

    session.rollback()
    created = session.scalars(select(Document).where(Document.id.not_in(existing_ids))).all()
    for document in created:
        storage.delete(document.storage_key)
        session.delete(document)
    session.commit()
    session.close()
