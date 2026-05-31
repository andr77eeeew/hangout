import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import CallbackQuery, Message, User
from bot.api_client import APIClient
from bot.handlers.link import cmd_link, cmd_status, cmd_unlink
from bot.handlers.notifications import cmd_notifications, handle_toggle_callback
from bot.handlers.start import cmd_help, cmd_start
from bot.middlewares.auth import AuthMiddleware


@pytest.mark.asyncio
async def test_cmd_start() -> None:
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    await cmd_start(message)
    message.answer.assert_called_once()
    args, _ = message.answer.call_args
    assert "Welcome" in args[0]


@pytest.mark.asyncio
async def test_cmd_help() -> None:
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    await cmd_help(message)
    message.answer.assert_called_once()
    args, _ = message.answer.call_args
    assert "Commands" in args[0]


@pytest.mark.asyncio
async def test_cmd_link_success() -> None:
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 12345

    client = AsyncMock(spec=APIClient)
    client.generate_link_code.return_value = "123456"

    await cmd_link(message, client)

    client.generate_link_code.assert_called_once_with(12345)
    message.answer.assert_called_once()
    args, _ = message.answer.call_args
    assert "123456" in args[0]


@pytest.mark.asyncio
async def test_cmd_link_failure() -> None:
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 12345

    client = AsyncMock(spec=APIClient)
    client.generate_link_code.side_effect = Exception("API error")

    await cmd_link(message, client)

    message.answer.assert_called_once_with(
        "❌ Failed to generate a linking code. Please try again later."
    )


@pytest.mark.asyncio
async def test_cmd_status_linked() -> None:
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    linked_user = {"id": 1, "username": "testuser", "telegram_id": "12345"}

    await cmd_status(message, linked_user=linked_user)

    message.answer.assert_called_once()
    args, _ = message.answer.call_args
    assert "testuser" in args[0]


@pytest.mark.asyncio
async def test_cmd_status_unlinked() -> None:
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()

    await cmd_status(message, linked_user=None)

    message.answer.assert_called_once()
    args, _ = message.answer.call_args
    assert "not linked" in args[0]


@pytest.mark.asyncio
async def test_cmd_unlink_success() -> None:
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 12345

    client = AsyncMock(spec=APIClient)
    client.unlink.return_value = True

    await cmd_unlink(message, client)

    client.unlink.assert_called_once_with(12345)
    message.answer.assert_called_once()
    args, _ = message.answer.call_args
    assert "unlinked" in args[0].lower()


@pytest.mark.asyncio
async def test_cmd_notifications_success() -> None:
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 12345

    client = AsyncMock(spec=APIClient)
    client.get_notification_preferences.return_value = {
        "user_id": 1,
        "membership_updates": True,
        "activity_reminders": False,
        "tag_subscriptions": True,
    }

    await cmd_notifications(message, client)

    client.get_notification_preferences.assert_called_once_with(12345)
    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    assert "Notification Preferences" in args[0]
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_handle_toggle_callback_success() -> None:
    callback = AsyncMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.from_user = MagicMock(spec=User)
    callback.from_user.id = 12345
    callback.data = "toggle:membership_updates"

    mock_message = AsyncMock(spec=Message)
    mock_message.edit_reply_markup = AsyncMock()
    callback.message = mock_message

    client = AsyncMock(spec=APIClient)
    client.get_notification_preferences.return_value = {
        "membership_updates": False,
        "activity_reminders": True,
        "tag_subscriptions": False,
    }
    client.update_notification_preferences.return_value = {
        "membership_updates": True,
        "activity_reminders": True,
        "tag_subscriptions": False,
    }

    await handle_toggle_callback(callback, client)

    client.get_notification_preferences.assert_called_once_with(12345)
    client.update_notification_preferences.assert_called_once_with(
        12345, {"membership_updates": True}
    )
    mock_message.edit_reply_markup.assert_called_once()
    callback.answer.assert_called_once_with("Preference updated!")


@pytest.mark.asyncio
async def test_auth_middleware_exempt_commands() -> None:
    client = AsyncMock(spec=APIClient)
    middleware = AuthMiddleware(client=client)

    handler = AsyncMock()
    event = AsyncMock(spec=Message)
    event.from_user = MagicMock(spec=User)
    event.from_user.id = 12345
    event.text = "/start"

    data = {}

    await middleware(handler, event, data)

    handler.assert_called_once_with(event, data)
    client.get_user_by_telegram_id.assert_not_called()


@pytest.mark.asyncio
async def test_auth_middleware_linked_user() -> None:
    client = AsyncMock(spec=APIClient)
    linked_user = {"id": 1, "username": "testuser", "telegram_id": "12345"}
    client.get_user_by_telegram_id.return_value = linked_user

    middleware = AuthMiddleware(client=client)

    handler = AsyncMock()
    event = AsyncMock(spec=Message)
    event.from_user = MagicMock(spec=User)
    event.from_user.id = 12345
    event.text = "/status"

    data = {}

    await middleware(handler, event, data)

    client.get_user_by_telegram_id.assert_called_once_with(12345)
    assert data["linked_user"] == linked_user
    handler.assert_called_once_with(event, data)


@pytest.mark.asyncio
async def test_auth_middleware_unlinked_user() -> None:
    client = AsyncMock(spec=APIClient)
    client.get_user_by_telegram_id.return_value = None

    middleware = AuthMiddleware(client=client)

    handler = AsyncMock()
    event = AsyncMock(spec=Message)
    event.answer = AsyncMock()
    event.from_user = MagicMock(spec=User)
    event.from_user.id = 12345
    event.text = "/status"

    data = {}

    await middleware(handler, event, data)

    client.get_user_by_telegram_id.assert_called_once_with(12345)
    assert "linked_user" not in data
    handler.assert_not_called()
    event.answer.assert_called_once()
    args, _ = event.answer.call_args
    assert "not linked" in args[0]
