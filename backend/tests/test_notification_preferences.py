from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.main import app
from app.models.notification_preferences import NotificationPreferences
from app.models.user import User
from app.services.notification import NotificationService


@pytest.fixture
def override_auth(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def test_get_preferences_default_lazy_creation(
    async_client, mock_db, mock_user, override_auth
):
    mock_result_empty = MagicMock()
    mock_result_empty.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_result_empty]

    response = await async_client.get("/user/notification-preferences")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == mock_user.id
    assert data["membership_updates"] is True
    assert data["activity_reminders"] is True
    assert data["tag_subscriptions"] is True
    assert data["report_updates"] is True


async def test_get_preferences_existing(
    async_client, mock_db, mock_user, override_auth
):
    prefs = NotificationPreferences(
        user_id=mock_user.id,
        membership_updates=False,
        activity_reminders=True,
        tag_subscriptions=False,
        report_updates=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = prefs
    mock_db.execute.side_effect = [mock_result]

    response = await async_client.get("/user/notification-preferences")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == mock_user.id
    assert data["membership_updates"] is False
    assert data["activity_reminders"] is True
    assert data["tag_subscriptions"] is False
    assert data["report_updates"] is True


async def test_patch_preferences_partial_update(
    async_client, mock_db, mock_user, override_auth
):
    prefs = NotificationPreferences(
        user_id=mock_user.id,
        membership_updates=True,
        activity_reminders=True,
        tag_subscriptions=True,
        report_updates=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = prefs
    mock_db.execute.side_effect = [mock_result]

    response = await async_client.patch(
        "/user/notification-preferences", json={"report_updates": False}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == mock_user.id
    assert data["membership_updates"] is True
    assert data["activity_reminders"] is True
    assert data["tag_subscriptions"] is True
    assert data["report_updates"] is False


async def test_notification_preferences_unauthenticated(async_client):
    app.dependency_overrides.pop(get_current_user, None)

    response = await async_client.get("/user/notification-preferences")
    assert response.status_code == 401

    response = await async_client.patch(
        "/user/notification-preferences", json={"membership_updates": False}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_notify_report_update_respects_preferences() -> None:
    db = AsyncMock(spec=AsyncSession)
    active_user = User(id=1, is_active=True, telegram_id="12345")
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = active_user
    db.execute.return_value = user_result

    # 1. Enabled case
    prefs_enabled = NotificationPreferences(user_id=1, report_updates=True)
    with (
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs_enabled,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await NotificationService.notify_report_update(
            user_id=1,
            report_id="60c72b2f9b1d8b2a1c8b4567",
            status="resolved",
            resolution="User banned",
            db=db,
        )
        mock_send.assert_called_once_with(
            "12345",
            "Your report <code>60c72b2f9b1d8b2a1c8b4567</code> has been <b>resolved</b>! Verdict: User banned.",
        )

    # 2. Disabled case
    prefs_disabled = NotificationPreferences(user_id=1, report_updates=False)
    with (
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs_disabled,
        ),
        patch.object(NotificationService, "send_telegram_message") as mock_send,
    ):
        await NotificationService.notify_report_update(
            user_id=1,
            report_id="60c72b2f9b1d8b2a1c8b4567",
            status="resolved",
            resolution="User banned",
            db=db,
        )
        mock_send.assert_not_called()
