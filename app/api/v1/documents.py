import uuid
from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from app.api.deps import DocumentServiceDep
from app.schemas.documents import DocumentResponse

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    service: DocumentServiceDep,
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    data = file.file.read()
    document = service.create(file.filename, file.content_type, data)
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: uuid.UUID, service: DocumentServiceDep) -> DocumentResponse:
    document = service.get(document_id)
    return DocumentResponse.model_validate(document)
