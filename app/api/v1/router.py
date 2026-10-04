from fastapi import APIRouter

# Versioned API router. Document and /ask routers get included here
# in later phases, e.g. api_router.include_router(documents_router).
api_router = APIRouter(prefix="/api/v1")
