from fastapi import APIRouter

from app.api.v1.info import router as info_router

# Versioned API router. Document and /ask routers get included here
# in later phases, e.g. api_router.include_router(documents_router).
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(info_router)
