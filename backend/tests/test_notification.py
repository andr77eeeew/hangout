from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification_preferences import NotificationPreferences
from app.models.user import User
from app.services.notification import NotificationService


@pytest.mark.asyncio
async def test_send_telegram_message_success() -> None:
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client

    with (
        patch.object(
            settings,
            "TELEGRAM_BOT_TOKEN",
            MagicMock(get_secret_value=lambda: "fake-token"),
        ),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        result = await NotificationService.send_telegram_message(
            "12345", "Hello HTML message!"
        )
        assert result is True
        mock_client.post.assert_called_once_with(
            "https://api.telegram.org/botfake-token/sendMessage",
            json={
                "chat_id": "12345",
                "text": "Hello HTML message!",
                "parse_mode": "HTML",
            },
            timeout=10.0,
        )


@pytest.mark.asyncio
async def test_send_telegram_message_missing_token() -> None:
    with patch.object(settings, "TELEGRAM_BOT_TOKEN", None):
        result = await NotificationService.send_telegram_message("12345", "Hello")
        assert result is False


@pytest.mark.asyncio
async def test_send_telegram_message_http_error() -> None:
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.HTTPError("Network failure")
    mock_client.__aenter__.return_value = mock_client

    with (
        patch.object(
            settings,
            "TELEGRAM_BOT_TOKEN",
            MagicMock(get_secret_value=lambda: "fake-token"),
        ),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        result = await NotificationService.send_telegram_message("12345", "Hello")
        assert result is False


@pytest.mark.asyncio
async def test_send_telegram_message_unexpected_error() -> None:
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = ValueError("Unexpected issue")
    mock_client.__aenter__.return_value = mock_client

    with (
        patch.object(
            settings,
            "TELEGRAM_BOT_TOKEN",
            MagicMock(get_secret_value=lambda: "fake-token"),
        ),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        result = await NotificationService.send_telegram_message("12345", "Hello")
        assert result is False


@pytest.mark.asyncio
async def test_notify_membership_change_user_inactive_or_no_telegram() -> None:
    db = AsyncMock(spec=AsyncSession)
    user_result = MagicMock()

    # Test case: User not found
    user_result.scalar_one_or_none.return_value = None
    db.execute.return_value = user_result

    with patch.object(NotificationService, "send_telegram_message") as mock_send:
        await NotificationService.notify_membership_change(1, "Hiking", "approved", db)
        mock_send.assert_not_called()

    # Test case: User inactive
    inactive_user = User(id=1, is_active=False, telegram_id="12345")
    user_result.scalar_one_or_none.return_value = inactive_user
    db.execute.return_value = user_result

    with patch.object(NotificationService, "send_telegram_message") as mock_send:
        await NotificationService.notify_membership_change(1, "Hiking", "approved", db)
        mock_send.assert_not_called()

    # Test case: User has no telegram id
    no_tg_user = User(id=1, is_active=True, telegram_id=None)
    user_result.scalar_one_or_none.return_value = no_tg_user
    db.execute.return_value = user_result

    with patch.object(NotificationService, "send_telegram_message") as mock_send:
        await NotificationService.notify_membership_change(1, "Hiking", "approved", db)
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_notify_membership_change_success_and_disabled() -> None:
    db = AsyncMock(spec=AsyncSession)
    active_user = User(id=1, is_active=True, telegram_id="12345")

    # 1. Success case (membership_updates enabled)
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = active_user
    db.execute.return_value = user_result

    prefs = NotificationPreferences(user_id=1, membership_updates=True)

    with (
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await NotificationService.notify_membership_change(1, "Hiking", "approved", db)
        mock_send.assert_called_once_with(
            "12345",
            "Your request to join the activity <b>Hiking</b> has been <b>approved</b>! 🎉",
        )

    # 2. Disabled case (membership_updates disabled)
    prefs_disabled = NotificationPreferences(user_id=1, membership_updates=False)

    with (
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs_disabled,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await NotificationService.notify_membership_change(1, "Hiking", "approved", db)
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_notify_activity_reminder_success_and_disabled() -> None:
    db = AsyncMock(spec=AsyncSession)
    active_user = User(id=1, is_active=True, telegram_id="12345")

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = active_user
    db.execute.return_value = user_result

    # 1. Success case (activity_reminders enabled)
    prefs = NotificationPreferences(user_id=1, activity_reminders=True)

    with (
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await NotificationService.notify_activity_reminder(
            1, "Hiking", "2026-06-01 10:00", db
        )
        mock_send.assert_called_once_with(
            "12345",
            "Reminder: Activity <b>Hiking</b> starts at <b>2026-06-01 10:00</b>! 🕒",
        )

    # 2. Disabled case (activity_reminders disabled)
    prefs_disabled = NotificationPreferences(user_id=1, activity_reminders=False)

    with (
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs_disabled,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await NotificationService.notify_activity_reminder(
            1, "Hiking", "2026-06-01 10:00", db
        )
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_notify_tag_match_success_and_disabled() -> None:
    db = AsyncMock(spec=AsyncSession)
    active_user = User(id=1, is_active=True, telegram_id="12345")

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = active_user
    db.execute.return_value = user_result

    # 1. Success case (tag_subscriptions enabled)
    prefs = NotificationPreferences(user_id=1, tag_subscriptions=True)

    with (
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await NotificationService.notify_tag_match(
            1, "Board Games Event", ["board games", "fun"], db
        )
        mock_send.assert_called_once_with(
            "12345",
            "New activity <b>Board Games Event</b> matching your favorite tags: <b>board games, fun</b> has been created! 🏷️",
        )

    # 2. Disabled case (tag_subscriptions disabled)
    prefs_disabled = NotificationPreferences(user_id=1, tag_subscriptions=False)

    with (
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs_disabled,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await NotificationService.notify_tag_match(
            1, "Board Games Event", ["board games", "fun"], db
        )
        mock_send.assert_not_called()
