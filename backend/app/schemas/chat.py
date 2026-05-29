from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

PyObjectId = Annotated[str, BeforeValidator(str)]


class MessageType(str, Enum):
    text = "text"
    system = "system"


class ClientChatMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("content", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class ChatMessageResponse(BaseModel):
    id: PyObjectId = Field(alias="_id")
    activity_id: PyObjectId
    user_id: int
    username: str
    avatar_url: str | None = None
    content: str
    message_type: MessageType
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, value: datetime) -> datetime:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class ChatHistoryResponse(BaseModel):
    items: list[ChatMessageResponse]
    next_cursor: str | None = None
    has_more: bool


class WebSocketSystemData(BaseModel):
    content: str
    type: str


class WebSocketMemberCountData(BaseModel):
    online_count: int


class WebSocketErrorData(BaseModel):
    detail: str


class WebSocketEnvelope(BaseModel):
    event: str
    data: (
        ChatMessageResponse
        | WebSocketSystemData
        | WebSocketMemberCountData
        | WebSocketErrorData
    )
