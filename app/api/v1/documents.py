import uuid
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status

from app.api.deps import DocumentServiceDep
from app.schemas.documents import DocumentListResponse, DocumentResponse
from app.services.documents import DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    service: DocumentServiceDep,
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    data = file.file.read()
    document = service.create(file.filename, file.content_type, data)
    return DocumentResponse.model_validate(document)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    service: DocumentServiceDep,
    limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    documents, total = service.list_documents(limit, offset)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: uuid.UUID, service: DocumentServiceDep) -> DocumentResponse:
    document = service.get(document_id)
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: uuid.UUID, service: DocumentServiceDep) -> None:
    service.delete(document_id)
