from fastapi import APIRouter

from app.api.deps import InfoServiceDep
from app.schemas.info import InfoResponse

router = APIRouter(tags=["info"])


@router.get("/info", response_model=InfoResponse)
def get_info(service: InfoServiceDep) -> InfoResponse:
    return service.get_info()
