from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, field_validator, model_validator


class ActivityTypes(str, Enum):
    open = "open"
    closed = "closed"


class ActivityFormats(str, Enum):
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


class CreateActivity(BaseModel):
    title: str
    type: ActivityTypes = ActivityTypes.open
    category: ActivityCategory
    date: datetime
    max_members: int
    format: ActivityFormats = ActivityFormats.online
    description: str
    tags: list[str]
    location: str | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for raw in tags:
            tag = raw.strip().lstrip("#").casefold()
            if not tag:
                continue
            if tag not in seen:
                seen.add(tag)
                normalized.append(tag)

        if not normalized:
            raise ValueError("At least one tag is required")
        if len(normalized) > 5:
            raise ValueError("No more than 5 tags are allowed")
        return normalized

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("date must include timezone")
        if value <= datetime.now(timezone.utc):
            raise ValueError("Date must be in the future")
        return value

    @model_validator(mode="after")
    def validate_location_for_offline(self):
        if self.format == ActivityFormats.offline and not self.location:
            if self.location is None or not self.location.strip():
                raise ValueError("location is required for offline activity")
        if self.location is not None and not self.location.strip():
            raise ValueError("Location must not be empty")
        return self

    @field_validator("max_members")
    @classmethod
    def validate_members(cls, v: int) -> int:
        if v > 20:
            raise ValueError("No more than 20 members are allowed")
        if v < 2:
            raise ValueError("At least 2 members are required")
        return v


class ActivityResponse(BaseModel):
    id: str
    title: str
    type: ActivityTypes
    category: ActivityCategory
    date: datetime
    max_members: int
    format: ActivityFormats
    description: str
    tags: list[str]
    creator_id: int
    created_at: datetime
    updated_at: datetime
    location: str | None = None


class ActivityUpdate(BaseModel):
    title: str | None = None
    date: datetime | None = None
    type: ActivityTypes | None = None
    category: ActivityCategory | None = None
    max_members: int | None = None
    format: ActivityFormats | None = None
    description: str | None = None
    location: str | None = None
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str] | None) -> list[str] | None:
        if tags is None:
            return None

        normalized: list[str] = []
        seen: set[str] = set()

        for raw in tags:
            tag = raw.strip().lstrip("#").casefold()
            if not tag:
                continue
            if tag not in seen:
                seen.add(tag)
                normalized.append(tag)

        if not normalized:
            raise ValueError("At least one tag is required")
        if len(normalized) > 5:
            raise ValueError("No more than 5 tags are allowed")
        return normalized

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None:
            raise ValueError("date must include timezone")
        if value <= datetime.now(timezone.utc):
            raise ValueError("Date must be in the future")
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

    @model_validator(mode="after")
    def validate_location_for_offline(self):
        if self.format == ActivityFormats.offline:
            if self.location is None or not self.location.strip():
                raise ValueError("location is required for offline activity")
        if self.location is not None and not self.location.strip():
            raise ValueError("Location must not be empty")
        return self
