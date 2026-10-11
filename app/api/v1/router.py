from fastapi import APIRouter

from app.api.v1.ask import router as ask_router
from app.api.v1.documents import router as documents_router
from app.api.v1.info import router as info_router
from app.api.v1.search import router as search_router

# Versioned API router. /search is the retrieval inspection endpoint;
# /ask is the question endpoint that adds Gemini and citations on top of it.
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(info_router)
api_router.include_router(documents_router)
api_router.include_router(search_router)
api_router.include_router(ask_router)
