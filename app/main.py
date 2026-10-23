import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import get_embedding_service
from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


def _preload_embedding_model() -> None:
    try:
        get_embedding_service().load()
    except Exception:
        # The API keeps running. The first question tries the load again and
        # shows the real error; /health/model stays "idle" until then.
        logger.exception("Embedding model preload failed")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if get_settings().preload_embedding_model:
        logger.info("Preloading the embedding model in the background")
        threading.Thread(
            target=_preload_embedding_model, name="embedding-preload", daemon=True
        ).start()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    register_error_handlers(app)

    app.include_router(health_router)  # operational, unversioned
    app.include_router(api_router)  # /api/v1/...

    logger.info("Application created (env=%s, version=%s)", settings.app_env, settings.app_version)
    return app


app = create_app()
