from datetime import datetime
from pydantic import BaseModel


class CreatorPreview(BaseModel):
    id: int
    username: str
    avatar_url: str | None = None


class ActivitySummary(BaseModel):
    id: str
    creator_id: int
    title: str
    description: str
    starts_at: datetime
    ends_at: datetime
    location: str | None = None
    online_link: str | None = None
    format: str
    category: str
    tags: list[str]
    current_members: int
    max_members: int | None = None
    creator: CreatorPreview | None = None
    status: str

    model_config = {"populate_by_name": True}


class ActivityDetails(ActivitySummary):
    pass


class MemberPreview(BaseModel):
    id: int
    username: str
    avatar_url: str | None = None


class MembershipSummary(BaseModel):
    id: str
    activity_id: str
    user_id: int
    status: str
    joined_at: datetime
    user_preview: MemberPreview | None = None

    model_config = {"populate_by_name": True}


class TagSummary(BaseModel):
    id: int
    name: str
    slug: str


class ReportDetails(BaseModel):
    id: str
    reporter_id: int
    reported_user_id: int
    activity_id: str | None = None
    chat_message_id: str | None = None
    reason: str
    status: str
    moderator_id: int | None = None
    moderator_notes: str | None = None
    resolution: str | None = None
    created_at: datetime
    updated_at: datetime
    taken_at: datetime | None = None
    resolved_at: datetime | None = None

    model_config = {"populate_by_name": True}


class ReportPage(BaseModel):
    items: list[ReportDetails]
    total: int | None = None
    next_cursor: str | None = None
    has_more: bool


class ActivityCreatePayload(BaseModel):
    title: str
    type: str = "open"
    format: str = "online"
    category: str
    description: str
    date: datetime
    max_members: int
    tags: list[str]
    location: str | None = None
    extra_data: dict[str, str | int | bool | None] | None = None


class ReportResolvePayload(BaseModel):
    resolution: str
    moderator_notes: str | None = None
    ban_user: bool = False
    ban_reason: str | None = None


class ReportDismissPayload(BaseModel):
    resolution: str
    moderator_notes: str | None = None
