import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from app.tasks.notifications import async_check_activity_reminders
from app.models.user import User
from app.models.notification_preferences import NotificationPreferences
from app.services.notification import NotificationService


class MockCursor:
    def __init__(self, data: list[dict]) -> None:
        self.data = data

    async def to_list(self, length: int) -> list[dict]:
        return self.data


class MockRedis:
    def __init__(self) -> None:
        self.keys: dict[str, str] = {}

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        if nx and key in self.keys:
            return None
        self.keys[key] = value
        return True


@pytest.mark.asyncio
async def test_async_check_activity_reminders_success() -> None:
    now = datetime.now(timezone.utc)
    activity_date = now + timedelta(hours=2)

    activity = {
        "_id": ObjectId(),
        "title": "Hiking Trip",
        "status": "active",
        "date": activity_date,
    }

    member = {
        "activity_id": activity["_id"],
        "user_id": 42,
        "status": "approved",
    }

    mock_activities_col = MagicMock()
    mock_activities_col.find.return_value = MockCursor([activity])

    mock_membership_col = MagicMock()
    mock_membership_col.find.return_value = MockCursor([member])

    mock_redis = MockRedis()

    mock_user = User(id=42, is_active=True, telegram_id="987654")
    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    mock_db.execute.return_value = mock_user_result

    prefs = NotificationPreferences(user_id=42, activity_reminders=True)

    with (
        patch(
            "app.tasks.notifications.get_activities_collection",
            return_value=mock_activities_col,
        ),
        patch(
            "app.tasks.notifications.get_membership_collection",
            return_value=mock_membership_col,
        ),
        patch("app.tasks.notifications.get_redis", return_value=mock_redis),
        patch("app.tasks.notifications.AsyncSessionLocal", return_value=mock_db),
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await async_check_activity_reminders()

        dedup_key = f"reminded:{str(activity['_id'])}"
        assert dedup_key in mock_redis.keys

        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        assert args[0] == "987654"
        assert "Hiking Trip" in args[1]


@pytest.mark.asyncio
async def test_async_check_activity_reminders_outside_window() -> None:
    mock_activities_col = MagicMock()
    mock_activities_col.find.return_value = MockCursor([])

    mock_membership_col = MagicMock()
    mock_redis = MockRedis()
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    with (
        patch(
            "app.tasks.notifications.get_activities_collection",
            return_value=mock_activities_col,
        ),
        patch(
            "app.tasks.notifications.get_membership_collection",
            return_value=mock_membership_col,
        ),
        patch("app.tasks.notifications.get_redis", return_value=mock_redis),
        patch("app.tasks.notifications.AsyncSessionLocal", return_value=mock_db),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await async_check_activity_reminders()

        mock_activities_col.find.assert_called_once()
        mock_membership_col.find.assert_not_called()
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_async_check_activity_reminders_deduplication() -> None:
    now = datetime.now(timezone.utc)
    activity_date = now + timedelta(hours=2)

    activity = {
        "_id": ObjectId(),
        "title": "Hiking Trip",
        "status": "active",
        "date": activity_date,
    }

    member = {
        "activity_id": activity["_id"],
        "user_id": 42,
        "status": "approved",
    }

    mock_activities_col = MagicMock()
    mock_activities_col.find.return_value = MockCursor([activity])

    mock_membership_col = MagicMock()
    mock_membership_col.find.return_value = MockCursor([member])

    mock_redis = MockRedis()

    mock_user = User(id=42, is_active=True, telegram_id="987654")
    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    mock_db.execute.return_value = mock_user_result

    prefs = NotificationPreferences(user_id=42, activity_reminders=True)

    with (
        patch(
            "app.tasks.notifications.get_activities_collection",
            return_value=mock_activities_col,
        ),
        patch(
            "app.tasks.notifications.get_membership_collection",
            return_value=mock_membership_col,
        ),
        patch("app.tasks.notifications.get_redis", return_value=mock_redis),
        patch("app.tasks.notifications.AsyncSessionLocal", return_value=mock_db),
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await async_check_activity_reminders()
        assert mock_send.call_count == 1

        await async_check_activity_reminders()
        assert mock_send.call_count == 1


@pytest.mark.asyncio
async def test_async_check_activity_reminders_preferences_disabled() -> None:
    now = datetime.now(timezone.utc)
    activity_date = now + timedelta(hours=2)

    activity = {
        "_id": ObjectId(),
        "title": "Hiking Trip",
        "status": "active",
        "date": activity_date,
    }

    member = {
        "activity_id": activity["_id"],
        "user_id": 42,
        "status": "approved",
    }

    mock_activities_col = MagicMock()
    mock_activities_col.find.return_value = MockCursor([activity])

    mock_membership_col = MagicMock()
    mock_membership_col.find.return_value = MockCursor([member])

    mock_redis = MockRedis()

    mock_user = User(id=42, is_active=True, telegram_id="987654")
    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    mock_db.execute.return_value = mock_user_result

    prefs = NotificationPreferences(user_id=42, activity_reminders=False)

    with (
        patch(
            "app.tasks.notifications.get_activities_collection",
            return_value=mock_activities_col,
        ),
        patch(
            "app.tasks.notifications.get_membership_collection",
            return_value=mock_membership_col,
        ),
        patch("app.tasks.notifications.get_redis", return_value=mock_redis),
        patch("app.tasks.notifications.AsyncSessionLocal", return_value=mock_db),
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await async_check_activity_reminders()
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_async_check_activity_reminders_no_telegram() -> None:
    now = datetime.now(timezone.utc)
    activity_date = now + timedelta(hours=2)

    activity = {
        "_id": ObjectId(),
        "title": "Hiking Trip",
        "status": "active",
        "date": activity_date,
    }

    member = {
        "activity_id": activity["_id"],
        "user_id": 42,
        "status": "approved",
    }

    mock_activities_col = MagicMock()
    mock_activities_col.find.return_value = MockCursor([activity])

    mock_membership_col = MagicMock()
    mock_membership_col.find.return_value = MockCursor([member])

    mock_redis = MockRedis()

    mock_user = User(id=42, is_active=True, telegram_id=None)
    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    mock_db.execute.return_value = mock_user_result

    prefs = NotificationPreferences(user_id=42, activity_reminders=True)

    with (
        patch(
            "app.tasks.notifications.get_activities_collection",
            return_value=mock_activities_col,
        ),
        patch(
            "app.tasks.notifications.get_membership_collection",
            return_value=mock_membership_col,
        ),
        patch("app.tasks.notifications.get_redis", return_value=mock_redis),
        patch("app.tasks.notifications.AsyncSessionLocal", return_value=mock_db),
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await async_check_activity_reminders()
        mock_send.assert_not_called()
