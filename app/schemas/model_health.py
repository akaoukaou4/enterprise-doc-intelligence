from typing import Literal

from pydantic import BaseModel


class ModelHealthResponse(BaseModel):
    # ready: loaded and checked. loading: a load is running. idle: not loaded yet.
    status: Literal["ready", "loading", "idle"]
