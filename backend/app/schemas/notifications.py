from pydantic import BaseModel


class NotificationPreferencesResponse(BaseModel):
    user_id: int
    membership_updates: bool
    activity_reminders: bool
    tag_subscriptions: bool

    model_config = {"from_attributes": True}


class NotificationPreferencesUpdate(BaseModel):
    membership_updates: bool | None = None
    activity_reminders: bool | None = None
    tag_subscriptions: bool | None = None
