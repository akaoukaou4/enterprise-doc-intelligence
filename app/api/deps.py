from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.info import InfoService

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_info_service(settings: AppSettings) -> InfoService:
    return InfoService(settings)


InfoServiceDep = Annotated[InfoService, Depends(get_info_service)]
