from pydantic import BaseModel, Field


class BanUserRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=1000)


class UnbanUserRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=1000)
