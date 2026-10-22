import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    # from_attributes lets Pydantic read a SQLAlchemy Document object directly.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    """One page of documents. total is the count of all documents, not of this page."""

    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int
