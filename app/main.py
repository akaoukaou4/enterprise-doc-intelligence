import logging

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    register_error_handlers(app)

    app.include_router(health_router)  # operational, unversioned
    app.include_router(api_router)  # /api/v1/...

    logger.info("Application created (env=%s, version=%s)", settings.app_env, settings.app_version)
    return app


app = create_app()
