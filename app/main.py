import logging

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(health_router)

    logger.info("Application created (env=%s, version=%s)", settings.app_env, settings.app_version)
    return app


app = create_app()
