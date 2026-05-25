from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Literal, Union

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


class CoverStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class GamePlatform(str, Enum):
    pc = "pc"
    playstation = "playstation"
    xbox = "xbox"
    nintendo = "nintendo"
    mobile = "mobile"
    cross_platform = "cross-platform"


class BoardGamesComplexity(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class SportSkillLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class MusicRole(str, Enum):
    listener = "listener"
    perfomer = "perfomer"
    jam = "jam"


class GameDetails(BaseModel):
    category: Literal[ActivityCategory.games] = ActivityCategory.games
    game_name: str
    platform: GamePlatform
    genre: str | None = None
    game_id: int | None = None
    cover_key: str | None = None
    cover_status: CoverStatus = CoverStatus.pending
    cover_url: str | None = None


class BoardGameDetails(BaseModel):
    category: Literal[ActivityCategory.board_games] = ActivityCategory.board_games
    game_name: str
    player_count: int | None = None
    complexity: BoardGamesComplexity | None = None


class MovieDetails(BaseModel):
    category: Literal[ActivityCategory.movies] = ActivityCategory.movies
    movie_name: str
    genre: str | None = None
    cinema: str | None = None  # name of cinema. Only for offline format


class AnimeDetails(BaseModel):
    category: Literal[ActivityCategory.anime] = ActivityCategory.anime
    anime_name: str
    episode_range: str | None = None
    genre: str | None = None


class SportDetails(BaseModel):
    category: Literal[ActivityCategory.sport] = ActivityCategory.sport
    sport_type: str
    skill_level: SportSkillLevel | None = None
    equipment_needed: bool | None = None


class MusicDetails(BaseModel):
    category: Literal[ActivityCategory.music] = ActivityCategory.music
    genre: str | None = None
    role: MusicRole | None = None


class ActivityCreatorPreview(BaseModel):
    id: int
    username: str
    avatar_key: str | None = None
    avatar_url: str | None = None


class GameCovers(BaseModel):
    id: PyObjectId = Field(alias="_id")
    game_id: int
    game_name: str
    game_slug: str
    cover_key: str | None = None
    rawg_url: str | None = None
    cover_status: CoverStatus
    fetched_at: datetime


class ActivityBase(BaseModel):
    title: str = Field(
        min_length=3,
        max_length=100,
        description="Title of the activity",
        json_schema_extra={"example": "Let's play Minecraft tonight!"},
    )
    type: ActivityType = Field(
        ActivityType.open,
        description="`open` — Anyone can join. `closed` — By invitation or link only.",
    )
    format: ActivityFormat = Field(
        ActivityFormat.online,
        description="Event format. If `offline`, the `location` field is required!",
    )
    category: ActivityCategory
    extra_data: Annotated[
        Union[
            GameDetails
            | BoardGameDetails
            | MovieDetails
            | AnimeDetails
            | SportDetails
            | MusicDetails
            | None
        ],
        Field(
            discriminator="category",
            description="""Category-specific details. 
                    🚨 **Attention, front-end developers:** Be sure to include the `category` field within this object! 
                    For example, for games: `{“category”: “games”, “game_name”: “Minecraft”, ‘platform’: “pc”}`.
                    For the `foods` category, pass `null`.""",
        ),
    ]
    description: str = Field(min_length=10, max_length=2000)
    date: datetime = Field(
        description="Date (must include the time zone and be at least 2 hours in the future)."
    )
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

    @model_validator(mode="after")
    def validate_extra_data(self):
        if self.category == "foods":
            if self.extra_data is not None:
                raise ValueError("For 'foods' category, extra_data must be null")
            return self

        if self.extra_data is None:
            raise ValueError(f"extra_data is required for {self.category} category")

        if self.category != self.extra_data.category:
            raise ValueError("Activity category must match extra_data category")

        return self


class ActivityCreate(ActivityBase):
    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "We urgently need a healer for the raid!",
                "type": "open",
                "format": "online",
                "category": "games",
                "extra_data": {
                    "category": "games",
                    "game_name": "World of Warcraft",
                    "platform": "pc",
                    "genre": "MMORPG",
                },
                "description": "Let's go take down the boss. We'll coordinate on Discord.",
                "date": "2026-05-10T18:00:00Z",
                "max_members": 5,
                "tags": ["wow", "mmo", "raid"],
                "location": None,
            }
        }
    }

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
