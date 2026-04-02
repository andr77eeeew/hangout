from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator

from app.schemas.validators import ValidTags

PyObjectId = Annotated[str, BeforeValidator(str)]


class ActivityType(str, Enum):
    open = "open"
    closed = "closed"


class ActivityFormat(str, Enum):
    online = "online"
    offline = "offline"


class ActivityCategory(str, Enum):
    games = "games"
    sport = "sport"
    board_games = "board_games"
    movies = "movies"
    foods = "foods"
    music = "music"
    anime = "anime"


class ActivityStatus(str, Enum):
    active = "active"
    completed = "completed"
    canceled = "canceled"
    expired = "expired"


class ActivityCreatorPreview(BaseModel):
    id: int
    username: str
    avatar_key: str | None = None
    avatar_url: str | None = None


class ActivityBase(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    type: ActivityType = ActivityType.open
    format: ActivityFormat = ActivityFormat.online
    category: ActivityCategory
    description: str = Field(min_length=10, max_length=2000)
    date: datetime
    max_members: int
    tags: ValidTags
    location: str | None = None

    @field_validator("max_members")
    @classmethod
    def validate_members(cls, value: int) -> int:
        if value < 2:
            raise ValueError("At least 2 members are required")
        if value > 20:
            raise ValueError("No more than 20 members are allowed")
        return value

    @field_validator("location", mode="before")
    @classmethod
    def normalize_location(cls, value):
        if value is None:
            return None

        if isinstance(value, str):
            cleaned = value.strip()

            return cleaned or None

        return value

    @model_validator(mode="after")
    def validate_location_for_offline(self):
        if self.format == ActivityFormat.offline and self.location is None:
            raise ValueError("location is required for offline activity")

        return self


class ActivityCreate(ActivityBase):
    @field_validator("date")
    @classmethod
    def validate_future_date(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("date must include timezone")

        value_utc = value.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)

        if value_utc <= now_utc:
            raise ValueError("Date and time must be in the future")

        if value_utc - now_utc < timedelta(hours=2):
            raise ValueError("Activity must be scheduled at least 2 hours in advance")
        return value


class ActivityResponse(ActivityBase):
    id: PyObjectId = Field(alias="_id")
    creator: ActivityCreatorPreview | None = None
    current_members: int
    status: ActivityStatus = ActivityStatus.active
    created_at: datetime
    updated_at: datetime

    @field_validator("date", "created_at", "updated_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "_id": "67e6e4b5a5c2f9a3f8de1111",
                "title": "Играем в Minecraft сегодня вечером",
                "type": "open | closed",
                "format": "online | offline",
                "category": "games | sport | movies | ...",
                "description": "Нужен 4й игрок, играем на выживание",
                "date": "2026-03-29T18:00:00+00:00",
                "max_members": 10,
                "tags": ["minecraft", "survival", "вечер"],
                "location": None,
                "creator_id": 1,
                "current_members": 2,
                "status": "active | completed | cancelled | expired",
                "created_at": "2026-03-28T16:00:00+00:00",
                "updated_at": "2026-03-28T16:00:00+00:00",
            }
        },
    }


class ActivityResponseFeed(BaseModel):
    items: list[ActivityResponse] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool


class ActivityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=100)
    date: datetime | None = None
    type: ActivityType | None = None
    category: ActivityCategory | None = None
    max_members: int | None = None
    format: ActivityFormat | None = None
    description: str | None = Field(default=None, min_length=10, max_length=2000)
    location: str | None = None
    tags: ValidTags | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None:
            raise ValueError("date must include timezone")

        value_utc = value.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)

        if value_utc <= now_utc:
            raise ValueError("Date and time must be in the future")

        if value_utc - now_utc < timedelta(hours=2):
            raise ValueError("Activity must be scheduled at least 2 hours in advance")

        return value

    @field_validator("max_members")
    @classmethod
    def validate_members(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v > 20:
            raise ValueError("No more than 20 members are allowed")
        if v < 2:
            raise ValueError("At least 2 members are required")
        return v

    @field_validator("location", mode="before")
    @classmethod
    def normalize_location(cls, value):
        if value is None:
            return None

        if isinstance(value, str):
            cleaned = value.strip()

            return cleaned or None

        return value

    @model_validator(mode="after")
    def validate_location_for_offline(self):
        # ВНИМАНИЕ: эта валидация проверяет только текущий payload.
        # Если format=offline приходит без location, и в БД location уже null —
        # итоговый документ будет невалидным. Полная валидация должна быть на уровне сервиса.
        if self.format == ActivityFormat.offline and self.location is None:
            raise ValueError("location is required for offline activity")

        return self
