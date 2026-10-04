import logging

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession
from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.schemas.health import DbHealthResponse, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        version=settings.app_version,
    )


@router.get("/health/db", response_model=DbHealthResponse)
def health_db(db: DbSession) -> DbHealthResponse:
    """Readiness check: can the app reach the database?"""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Database health check failed: %s", exc)
        raise ExternalServiceError("Database is not reachable") from exc
    return DbHealthResponse(status="ok", database="ok")
