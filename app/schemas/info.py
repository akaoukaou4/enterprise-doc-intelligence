from pydantic import BaseModel


class InfoResponse(BaseModel):
    name: str
    version: str
    environment: str
