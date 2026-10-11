from fastapi import APIRouter

from app.api.deps import RagServiceDep
from app.schemas.ask import AskCitation, AskRequest, AskResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, rag: RagServiceDep) -> AskResponse:
    """Answer a question from the stored documents, with citations.

    Clients decide how to display the result from `found`, never from the answer
    text. When `found` is false there are no citations. A plain `def`, so FastAPI
    runs the blocking embedding and Gemini calls in a thread pool.
    """
    result = rag.ask(body.question, body.top_k)
    return AskResponse(
        answer=result.answer,
        found=result.found,
        citations=[AskCitation.model_validate(citation) for citation in result.citations],
    )
