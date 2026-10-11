import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.services.retrieval import DEFAULT_TOP_K, MAX_QUESTION_CHARS, MAX_TOP_K


class AskRequest(BaseModel):
    # Strip first, so a whitespace-only question becomes "" and fails min_length.
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)


class AskCitation(BaseModel):
    # from_attributes lets Pydantic read the Citation dataclass directly.
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    filename: str
    page_numbers: list[int]
    heading: str | None
    text: str


class AskResponse(BaseModel):
    answer: str
    found: bool
    citations: list[AskCitation]
