import re
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

PyObjectId = Annotated[str, BeforeValidator(str)]


class ReportStatus(str, Enum):
    open = "open"
    in_review = "in_review"
    resolved = "resolved"
    dismissed = "dismissed"


class ReportCreate(BaseModel):
    reported_user_id: int
    activity_id: str | None = None
    chat_message_id: str | None = None
    reason: str = Field(..., min_length=10, max_length=1000)

    @field_validator("activity_id", "chat_message_id")
    @classmethod
    def validate_object_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if not re.match(r"^[0-9a-fA-F]{24}$", cleaned):
            raise ValueError("Must be a valid 24-character hexadecimal string")
        return cleaned


class ReportResponse(BaseModel):
    id: PyObjectId = Field(alias="_id")
    reporter_id: int
    reported_user_id: int
    activity_id: PyObjectId | None = None
    chat_message_id: PyObjectId | None = None
    reason: str
    status: ReportStatus
    moderator_id: int | None = None
    moderator_notes: str | None = None
    resolution: str | None = None
    created_at: datetime
    updated_at: datetime
    taken_at: datetime | None = None
    resolved_at: datetime | None = None

    @field_validator(
        "created_at", "updated_at", "taken_at", "resolved_at", mode="before"
    )
    @classmethod
    def ensure_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class ReportTakeResponse(BaseModel):
    report: ReportResponse


class ReportResolve(BaseModel):
    resolution: str = Field(..., min_length=5, max_length=1000)
    moderator_notes: str | None = Field(default=None, max_length=1000)
    ban_user: bool = False
    ban_reason: str | None = Field(default=None, max_length=1000)


class ReportDismiss(BaseModel):
    resolution: str = Field(..., min_length=5, max_length=1000)
    moderator_notes: str | None = Field(default=None, max_length=1000)


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int | None = None
    next_cursor: str | None = None
    has_more: bool
