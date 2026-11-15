from pydantic import BaseModel, Field


class RequeueRequest(BaseModel):
    max_attempts: int = Field(default=3, ge=1)
