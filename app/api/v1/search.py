from fastapi import APIRouter

from app.api.deps import RetrievalServiceDep
from app.schemas.search import SearchHit, SearchRequest, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


# A plain `def` (not `async def`): embedding is blocking CPU work, and FastAPI
# runs `def` routes in a thread pool so the server stays responsive.
@router.post("", response_model=SearchResponse)
def search(request: SearchRequest, service: RetrievalServiceDep) -> SearchResponse:
    hits = service.search(request.question, request.top_k)
    return SearchResponse(results=[SearchHit.model_validate(hit) for hit in hits])
