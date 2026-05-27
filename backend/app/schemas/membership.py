from datetime import datetime
from enum import Enum
from typing import Annotated
from pydantic import BaseModel, BeforeValidator, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class MembershipStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    left = "left"
    kicked = "kicked"


class MemberPreview(BaseModel):
    id: int
    username: str
    avatar_url: str | None = None


class MembershipResponse(BaseModel):
    id: PyObjectId = Field(alias="_id")
    activity_id: PyObjectId
    user_id: int
    status: MembershipStatus
    joined_at: datetime
    user_preview: MemberPreview | None = None


class MembershipListResponse(BaseModel):
    items: list[MembershipResponse]
    total: int
