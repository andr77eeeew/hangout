from unittest.mock import MagicMock

import pytest

from app.core.dependencies import get_current_user
from app.main import app
from app.models.notification_preferences import NotificationPreferences


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


async def test_get_preferences_existing(
    async_client, mock_db, mock_user, override_auth
):
    prefs = NotificationPreferences(
        user_id=mock_user.id,
        membership_updates=False,
        activity_reminders=True,
        tag_subscriptions=False,
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


async def test_patch_preferences_partial_update(
    async_client, mock_db, mock_user, override_auth
):
    prefs = NotificationPreferences(
        user_id=mock_user.id,
        membership_updates=True,
        activity_reminders=True,
        tag_subscriptions=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = prefs
    mock_db.execute.side_effect = [mock_result]

    response = await async_client.patch(
        "/user/notification-preferences", json={"membership_updates": False}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == mock_user.id
    assert data["membership_updates"] is False
    assert data["activity_reminders"] is True
    assert data["tag_subscriptions"] is True


async def test_notification_preferences_unauthenticated(async_client):
    app.dependency_overrides.pop(get_current_user, None)

    response = await async_client.get("/user/notification-preferences")
    assert response.status_code == 401

    response = await async_client.patch(
        "/user/notification-preferences", json={"membership_updates": False}
    )
    assert response.status_code == 401
