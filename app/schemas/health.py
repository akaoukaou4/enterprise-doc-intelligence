from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str


class DbHealthResponse(BaseModel):
    status: str
    database: str
