from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.documents import DocumentService
from app.services.info import InfoService
from app.services.storage import StorageService

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_info_service(settings: AppSettings) -> InfoService:
    return InfoService(settings)


InfoServiceDep = Annotated[InfoService, Depends(get_info_service)]


def get_storage_service(settings: AppSettings) -> StorageService:
    return StorageService(settings)


StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]


def get_document_service(
    settings: AppSettings, db: DbSession, storage: StorageServiceDep
) -> DocumentService:
    return DocumentService(settings, db, storage)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
