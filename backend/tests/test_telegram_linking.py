import json
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from app.core.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.models.notification_preferences import NotificationPreferences
from app.services.telegram_linking import TelegramLinkingService


@pytest.fixture
def override_auth(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


# -------------------------------------------------------------
# 1. UNIT TESTS FOR SERVICE LAYER
# -------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_link_code_success(mock_redis) -> None:
    mock_redis.set.return_value = True

    code = await TelegramLinkingService.generate_link_code("123456789", mock_redis)

    assert len(code) == 6
    assert code.isdigit()
    mock_redis.set.assert_called_once()
    args, kwargs = mock_redis.set.call_args
    assert args[0] == f"tg_link:{code}"
    assert json.loads(args[1]) == {"telegram_user_id": "123456789"}
    assert kwargs["ex"] == 300
    assert kwargs["nx"] is True


@pytest.mark.asyncio
async def test_generate_link_code_collision_retry(mock_redis) -> None:
    # First 2 calls fail (nx collision), 3rd call succeeds
    mock_redis.set.side_effect = [False, False, True]

    code = await TelegramLinkingService.generate_link_code("123456789", mock_redis)

    assert len(code) == 6
    assert mock_redis.set.call_count == 3


@pytest.mark.asyncio
async def test_generate_link_code_all_collisions_fail(mock_redis) -> None:
    mock_redis.set.return_value = False

    with pytest.raises(HTTPException) as exc_info:
        await TelegramLinkingService.generate_link_code("123456789", mock_redis)

    assert exc_info.value.status_code == 500
    assert "Failed to generate a unique linking code" in exc_info.value.detail
    assert mock_redis.set.call_count == 5


# -------------------------------------------------------------
# 2. INTEGRATION TESTS FOR PUBLIC ENDPOINTS
# -------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_telegram_link_status_unlinked(
    async_client, override_auth, mock_user
) -> None:
    mock_user.telegram_id = None
    response = await async_client.get("/user/telegram-link")
    assert response.status_code == 200
    data = response.json()
    assert data["is_linked"] is False
    assert data["telegram_id"] is None


@pytest.mark.asyncio
async def test_get_telegram_link_status_linked(
    async_client, override_auth, mock_user
) -> None:
    mock_user.telegram_id = "987654321"
    response = await async_client.get("/user/telegram-link")
    assert response.status_code == 200
    data = response.json()
    assert data["is_linked"] is True
    assert data["telegram_id"] == "987654321"


@pytest.mark.asyncio
async def test_link_telegram_success(
    async_client, override_auth, mock_db, mock_redis, mock_user
) -> None:
    # Mock Redis GETDEL returning valid link info
    mock_redis.getdel.return_value = json.dumps({"telegram_user_id": "123456"})

    # Mock DB query checks
    # 1st query: check if Telegram ID is linked to another user (returns None)
    # 2nd query: fetch current user
    mock_res_other = MagicMock()
    mock_res_other.scalar_one_or_none.return_value = None

    mock_res_user = MagicMock()
    mock_res_user.scalar_one.return_value = mock_user

    mock_res_prefs = MagicMock()
    mock_res_prefs.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [mock_res_other, mock_res_user, mock_res_prefs]

    response = await async_client.post("/user/link-telegram", json={"code": "112233"})
    assert response.status_code == 200
    data = response.json()
    assert data["is_linked"] is True
    assert data["telegram_id"] == "123456"
    assert mock_user.telegram_id == "123456"


@pytest.mark.asyncio
async def test_link_telegram_invalid_code(
    async_client, override_auth, mock_redis
) -> None:
    mock_redis.getdel.return_value = None

    response = await async_client.post("/user/link-telegram", json={"code": "112233"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired link code"


@pytest.mark.asyncio
async def test_link_telegram_validation_error(async_client, override_auth) -> None:
    # Code must be exactly 6 digits
    response = await async_client.post("/user/link-telegram", json={"code": "12345"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_link_telegram_conflict(
    async_client, override_auth, mock_db, mock_redis, mock_user
) -> None:
    mock_redis.getdel.return_value = json.dumps({"telegram_user_id": "123456"})

    # Another user exists with the same telegram ID
    another_user = User(
        id=2, username="another", email="another@user.com", telegram_id="123456"
    )
    mock_res_other = MagicMock()
    mock_res_other.scalar_one_or_none.return_value = another_user

    mock_db.execute.side_effect = [mock_res_other]

    response = await async_client.post("/user/link-telegram", json={"code": "112233"})
    assert response.status_code == 409
    assert (
        response.json()["detail"] == "Telegram account already linked to another user"
    )


@pytest.mark.asyncio
async def test_unlink_telegram_public(
    async_client, override_auth, mock_db, mock_user
) -> None:
    mock_user.telegram_id = "123456"

    mock_res_user = MagicMock()
    mock_res_user.scalar_one.return_value = mock_user
    mock_db.execute.return_value = mock_res_user

    response = await async_client.delete("/user/link-telegram")
    assert response.status_code == 200
    data = response.json()
    assert data["is_linked"] is False
    assert data["telegram_id"] is None
    assert mock_user.telegram_id is None


# -------------------------------------------------------------
# 3. INTEGRATION TESTS FOR INTERNAL API (BOT)
# -------------------------------------------------------------


@pytest.mark.asyncio
async def test_internal_link_code_generation(async_client, mock_redis) -> None:
    mock_redis.set.return_value = True

    response = await async_client.post(
        "/internal/telegram/link-code",
        json={"telegram_user_id": "123456"},
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert response.status_code == 200
    assert len(response.json()["code"]) == 6


@pytest.mark.asyncio
async def test_internal_get_user_by_telegram_id_success(
    async_client, mock_db, mock_user
) -> None:
    mock_user.telegram_id = "123456"
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_res

    response = await async_client.get(
        "/internal/telegram/users/123456",
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == mock_user.id
    assert data["username"] == mock_user.username
    assert data["telegram_id"] == "123456"


@pytest.mark.asyncio
async def test_internal_get_user_by_telegram_id_404(async_client, mock_db) -> None:
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    response = await async_client.get(
        "/internal/telegram/users/123456",
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert response.status_code == 404
    assert (
        response.json()["detail"] == "Hangout user not found for the given telegram_id"
    )


@pytest.mark.asyncio
async def test_internal_get_preferences_success(
    async_client, mock_db, mock_user
) -> None:
    mock_user.telegram_id = "123456"
    mock_res_user = MagicMock()
    mock_res_user.scalar_one_or_none.return_value = mock_user

    prefs = NotificationPreferences(
        user_id=mock_user.id,
        membership_updates=True,
        activity_reminders=False,
        tag_subscriptions=True,
    )
    mock_res_prefs = MagicMock()
    mock_res_prefs.scalar_one_or_none.return_value = prefs

    mock_db.execute.side_effect = [mock_res_user, mock_res_prefs]

    response = await async_client.get(
        "/internal/telegram/users/123456/notification-preferences",
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == mock_user.id
    assert data["activity_reminders"] is False
    assert data["membership_updates"] is True


@pytest.mark.asyncio
async def test_internal_patch_preferences_success(
    async_client, mock_db, mock_user
) -> None:
    mock_user.telegram_id = "123456"
    mock_res_user = MagicMock()
    mock_res_user.scalar_one_or_none.return_value = mock_user

    prefs = NotificationPreferences(
        user_id=mock_user.id,
        membership_updates=True,
        activity_reminders=False,
        tag_subscriptions=True,
    )
    mock_res_prefs = MagicMock()
    mock_res_prefs.scalar_one_or_none.return_value = prefs

    mock_db.execute.side_effect = [mock_res_user, mock_res_prefs]

    response = await async_client.patch(
        "/internal/telegram/users/123456/notification-preferences",
        json={"activity_reminders": True},
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["activity_reminders"] is True


@pytest.mark.asyncio
async def test_internal_unlink_success(async_client, mock_db, mock_user) -> None:
    mock_user.telegram_id = "123456"
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_res

    response = await async_client.delete(
        "/internal/telegram/users/123456/link",
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Unlinked successfully"}
    assert mock_user.telegram_id is None


@pytest.mark.asyncio
async def test_internal_api_key_protection_missing(async_client) -> None:
    # Post without header should fail
    response = await async_client.post(
        "/internal/telegram/link-code", json={"telegram_user_id": "123456"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid internal API key"


@pytest.mark.asyncio
async def test_internal_api_key_protection_invalid(async_client) -> None:
    # Post with wrong header should fail
    response = await async_client.post(
        "/internal/telegram/link-code",
        json={"telegram_user_id": "123456"},
        headers={"X-Internal-Key": "wrong_key"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid internal API key"
