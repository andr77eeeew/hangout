from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.models.user import User
from app.schemas.chat import MessageType
from app.services.chat import ChatService


@pytest.fixture(autouse=True)
def clean_ws_manager() -> None:
    from app.core.ws_manager import connection_manager

    connection_manager._rooms.clear()


@pytest.mark.asyncio
async def test_verify_chat_access_success() -> None:
    user_id = 1
    activity_id = str(ObjectId())

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId(activity_id),
        "status": "active",
    }

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = {
        "activity_id": ObjectId(activity_id),
        "user_id": user_id,
        "status": "approved",
    }

    result = await ChatService.verify_chat_access(
        user_id=user_id,
        activity_id=activity_id,
        activities_col=mock_activities_col,
        membership_col=mock_membership_col,
    )

    assert result["_id"] == ObjectId(activity_id)
    mock_activities_col.find_one.assert_called_once_with({"_id": ObjectId(activity_id)})
    mock_membership_col.find_one.assert_called_once_with(
        {
            "activity_id": ObjectId(activity_id),
            "user_id": user_id,
            "status": "approved",
        }
    )


@pytest.mark.asyncio
async def test_verify_chat_access_invalid_activity_id() -> None:
    user_id = 1
    activity_id = "invalid_id"
    mock_activities_col = AsyncMock()
    mock_membership_col = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await ChatService.verify_chat_access(
            user_id=user_id,
            activity_id=activity_id,
            activities_col=mock_activities_col,
            membership_col=mock_membership_col,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid activity id"


@pytest.mark.asyncio
async def test_verify_chat_access_activity_not_found() -> None:
    user_id = 1
    activity_id = str(ObjectId())

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = None
    mock_membership_col = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await ChatService.verify_chat_access(
            user_id=user_id,
            activity_id=activity_id,
            activities_col=mock_activities_col,
            membership_col=mock_membership_col,
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Activity not found"


@pytest.mark.asyncio
async def test_verify_chat_access_activity_not_active() -> None:
    user_id = 1
    activity_id = str(ObjectId())

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId(activity_id),
        "status": "completed",
    }
    mock_membership_col = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await ChatService.verify_chat_access(
            user_id=user_id,
            activity_id=activity_id,
            activities_col=mock_activities_col,
            membership_col=mock_membership_col,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Activity is not active"


@pytest.mark.asyncio
async def test_verify_chat_access_not_approved_member() -> None:
    user_id = 1
    activity_id = str(ObjectId())

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId(activity_id),
        "status": "active",
    }

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await ChatService.verify_chat_access(
            user_id=user_id,
            activity_id=activity_id,
            activities_col=mock_activities_col,
            membership_col=mock_membership_col,
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User is not an approved member of this activity"


@pytest.mark.asyncio
async def test_save_message_success() -> None:
    user_id = 1
    activity_id = str(ObjectId())
    content = "  Hello world!  "

    mock_user = User(
        id=user_id,
        username="testuser",
        avatar="avatars/user1.jpg",
    )

    mock_db = AsyncMock()
    mock_db.get.return_value = mock_user

    mock_s3_sign = MagicMock()
    mock_s3_sign.generate_presigned_url.return_value = "http://fake-s3/user1.jpg"

    mock_chat_col = AsyncMock()

    result = await ChatService.save_message(
        user_id=user_id,
        activity_id=activity_id,
        content=content,
        chat_col=mock_chat_col,
        db=mock_db,
        s3_public_sign=mock_s3_sign,
    )

    assert result.content == "Hello world!"
    assert result.username == "testuser"
    assert result.avatar_url == "http://fake-s3/user1.jpg"
    assert result.message_type == MessageType.text
    assert result.user_id == user_id
    assert str(result.activity_id) == activity_id

    mock_chat_col.insert_one.assert_called_once()
    inserted_doc = mock_chat_col.insert_one.call_args[0][0]
    assert inserted_doc["content"] == "Hello world!"
    assert inserted_doc["username"] == "testuser"
    assert inserted_doc["avatar_url"] == "http://fake-s3/user1.jpg"
    assert inserted_doc["activity_id"] == ObjectId(activity_id)


@pytest.mark.asyncio
async def test_save_message_empty_content() -> None:
    user_id = 1
    activity_id = str(ObjectId())
    mock_chat_col = AsyncMock()
    mock_db = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await ChatService.save_message(
            user_id=user_id,
            activity_id=activity_id,
            content="   ",
            chat_col=mock_chat_col,
            db=mock_db,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Message content cannot be empty"


@pytest.mark.asyncio
async def test_save_message_too_long() -> None:
    user_id = 1
    activity_id = str(ObjectId())
    mock_chat_col = AsyncMock()
    mock_db = AsyncMock()
    too_long_content = "a" * 2001

    with pytest.raises(HTTPException) as exc_info:
        await ChatService.save_message(
            user_id=user_id,
            activity_id=activity_id,
            content=too_long_content,
            chat_col=mock_chat_col,
            db=mock_db,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Message content is too long"


@pytest.mark.asyncio
async def test_save_message_user_not_found() -> None:
    user_id = 1
    activity_id = str(ObjectId())
    mock_chat_col = AsyncMock()

    mock_db = AsyncMock()
    mock_db.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await ChatService.save_message(
            user_id=user_id,
            activity_id=activity_id,
            content="valid content",
            chat_col=mock_chat_col,
            db=mock_db,
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found"


@pytest.mark.asyncio
async def test_get_history_invalid_activity_id() -> None:
    mock_chat_col = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await ChatService.get_history(
            activity_id="invalid_id",
            chat_col=mock_chat_col,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid activity id"


@pytest.mark.asyncio
async def test_get_history_invalid_cursor() -> None:
    mock_chat_col = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await ChatService.get_history(
            activity_id=str(ObjectId()),
            chat_col=mock_chat_col,
            cursor="invalid_cursor",
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid cursor"


@pytest.mark.asyncio
async def test_get_history_empty() -> None:
    activity_id = str(ObjectId())
    mock_chat_col = AsyncMock()

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=[]
    )
    mock_chat_col.find = MagicMock(return_value=mock_cursor)

    result = await ChatService.get_history(
        activity_id=activity_id,
        chat_col=mock_chat_col,
    )

    assert len(result.items) == 0
    assert result.has_more is False
    assert result.next_cursor is None

    mock_chat_col.find.assert_called_once_with({"activity_id": ObjectId(activity_id)})


@pytest.mark.asyncio
async def test_get_history_pagination_has_more() -> None:
    activity_id = str(ObjectId())
    mock_chat_col = AsyncMock()

    msg_ids = [ObjectId() for _ in range(3)]
    messages_db = [
        {
            "_id": msg_ids[0],
            "activity_id": ObjectId(activity_id),
            "user_id": 1,
            "username": "user1",
            "avatar_url": None,
            "content": "msg 1",
            "message_type": "text",
            "created_at": datetime.now(timezone.utc),
        },
        {
            "_id": msg_ids[1],
            "activity_id": ObjectId(activity_id),
            "user_id": 2,
            "username": "user2",
            "avatar_url": None,
            "content": "msg 2",
            "message_type": "text",
            "created_at": datetime.now(timezone.utc),
        },
        {
            "_id": msg_ids[2],
            "activity_id": ObjectId(activity_id),
            "user_id": 3,
            "username": "user3",
            "avatar_url": None,
            "content": "msg 3",
            "message_type": "text",
            "created_at": datetime.now(timezone.utc),
        },
    ]

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=messages_db
    )
    mock_chat_col.find = MagicMock(return_value=mock_cursor)

    result = await ChatService.get_history(
        activity_id=activity_id,
        chat_col=mock_chat_col,
        limit=2,
    )

    assert len(result.items) == 2
    assert result.has_more is True
    assert result.next_cursor == str(msg_ids[1])
    assert result.items[0].content == "msg 1"
    assert result.items[1].content == "msg 2"


@pytest.mark.asyncio
async def test_get_history_pagination_with_cursor() -> None:
    activity_id = str(ObjectId())
    cursor_id = str(ObjectId())
    mock_chat_col = AsyncMock()

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=[]
    )
    mock_chat_col.find = MagicMock(return_value=mock_cursor)

    result = await ChatService.get_history(
        activity_id=activity_id,
        chat_col=mock_chat_col,
        limit=5,
        cursor=cursor_id,
    )

    assert len(result.items) == 0
    assert result.has_more is False
    assert result.next_cursor is None

    mock_chat_col.find.assert_called_once_with(
        {
            "activity_id": ObjectId(activity_id),
            "_id": {"$lt": ObjectId(cursor_id)},
        }
    )


@pytest.mark.asyncio
async def test_get_current_user_ws_success() -> None:
    import jwt
    from app.core.config import settings
    from app.core.dependencies import get_current_user_ws

    user_id = 42
    mock_user = User(
        id=user_id,
        username="ws_user",
        is_active=True,
    )

    token = jwt.encode(
        {"sub": str(user_id), "type": "access"},
        settings.SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )

    mock_ws = AsyncMock()
    mock_ws.query_params = {"token": token}

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    user = await get_current_user_ws(websocket=mock_ws, db=mock_db)

    assert user == mock_user
    mock_ws.close.assert_not_called()


@pytest.mark.asyncio
async def test_get_current_user_ws_missing_token() -> None:
    from fastapi import WebSocketException
    from app.core.dependencies import get_current_user_ws

    mock_ws = AsyncMock()
    mock_ws.query_params = {}

    mock_db = AsyncMock()

    with pytest.raises(WebSocketException) as exc_info:
        await get_current_user_ws(websocket=mock_ws, db=mock_db)

    assert exc_info.value.code == 4001
    assert exc_info.value.reason == "Token missing"
    mock_ws.close.assert_called_once_with(code=4001)


@pytest.mark.asyncio
async def test_get_current_user_ws_invalid_token_signature() -> None:
    from fastapi import WebSocketException
    from app.core.dependencies import get_current_user_ws

    mock_ws = AsyncMock()
    mock_ws.query_params = {"token": "invalid.token.signature"}

    mock_db = AsyncMock()

    with pytest.raises(WebSocketException) as exc_info:
        await get_current_user_ws(websocket=mock_ws, db=mock_db)

    assert exc_info.value.code == 4001
    assert exc_info.value.reason == "Invalid token"
    mock_ws.close.assert_called_once_with(code=4001)


@pytest.mark.asyncio
async def test_get_current_user_ws_wrong_token_type() -> None:
    import jwt
    from fastapi import WebSocketException
    from app.core.config import settings
    from app.core.dependencies import get_current_user_ws

    user_id = 42
    token = jwt.encode(
        {"sub": str(user_id), "type": "refresh"},
        settings.SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )

    mock_ws = AsyncMock()
    mock_ws.query_params = {"token": token}

    mock_db = AsyncMock()

    with pytest.raises(WebSocketException) as exc_info:
        await get_current_user_ws(websocket=mock_ws, db=mock_db)

    assert exc_info.value.code == 4001
    assert exc_info.value.reason == "Invalid token type"
    mock_ws.close.assert_called_once_with(code=4001)


@pytest.mark.asyncio
async def test_get_current_user_ws_invalid_user_id_in_sub() -> None:
    import jwt
    from fastapi import WebSocketException
    from app.core.config import settings
    from app.core.dependencies import get_current_user_ws

    token = jwt.encode(
        {"sub": "not_an_int", "type": "access"},
        settings.SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )

    mock_ws = AsyncMock()
    mock_ws.query_params = {"token": token}

    mock_db = AsyncMock()

    with pytest.raises(WebSocketException) as exc_info:
        await get_current_user_ws(websocket=mock_ws, db=mock_db)

    assert exc_info.value.code == 4001
    assert exc_info.value.reason == "Invalid user ID"
    mock_ws.close.assert_called_once_with(code=4001)


@pytest.mark.asyncio
async def test_get_current_user_ws_user_not_found() -> None:
    import jwt
    from fastapi import WebSocketException
    from app.core.config import settings
    from app.core.dependencies import get_current_user_ws

    user_id = 42
    token = jwt.encode(
        {"sub": str(user_id), "type": "access"},
        settings.SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )

    mock_ws = AsyncMock()
    mock_ws.query_params = {"token": token}

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(WebSocketException) as exc_info:
        await get_current_user_ws(websocket=mock_ws, db=mock_db)

    assert exc_info.value.code == 4001
    assert exc_info.value.reason == "User inactive or not found"
    mock_ws.close.assert_called_once_with(code=4001)


@pytest.mark.asyncio
async def test_get_current_user_ws_user_inactive() -> None:
    import jwt
    from fastapi import WebSocketException
    from app.core.config import settings
    from app.core.dependencies import get_current_user_ws

    user_id = 42
    mock_user = User(
        id=user_id,
        username="ws_user",
        is_active=False,
    )

    token = jwt.encode(
        {"sub": str(user_id), "type": "access"},
        settings.SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )

    mock_ws = AsyncMock()
    mock_ws.query_params = {"token": token}

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    with pytest.raises(WebSocketException) as exc_info:
        await get_current_user_ws(websocket=mock_ws, db=mock_db)

    assert exc_info.value.code == 4001
    assert exc_info.value.reason == "User inactive or not found"
    mock_ws.close.assert_called_once_with(code=4001)


@pytest.mark.asyncio
async def test_connection_manager_connect_disconnect() -> None:
    from app.core.ws_manager import ConnectionManager

    manager = ConnectionManager()
    ws = AsyncMock()
    activity_id = "activity_1"
    user_id = 123

    await manager.connect(ws, activity_id, user_id)
    assert await manager.get_room_connection_count(activity_id) == 1
    assert await manager.get_room_user_count(activity_id) == 1

    await manager.disconnect(ws, activity_id, user_id)
    assert await manager.get_room_connection_count(activity_id) == 0
    assert await manager.get_room_user_count(activity_id) == 0
    assert activity_id not in manager._rooms


@pytest.mark.asyncio
async def test_connection_manager_multi_tab() -> None:
    from app.core.ws_manager import ConnectionManager

    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    activity_id = "activity_1"
    user_id = 123

    await manager.connect(ws1, activity_id, user_id)
    await manager.connect(ws2, activity_id, user_id)

    assert await manager.get_room_connection_count(activity_id) == 2
    assert await manager.get_room_user_count(activity_id) == 1

    await manager.disconnect(ws1, activity_id, user_id)
    assert await manager.get_room_connection_count(activity_id) == 1
    assert await manager.get_room_user_count(activity_id) == 1

    await manager.disconnect(ws2, activity_id, user_id)
    assert await manager.get_room_connection_count(activity_id) == 0
    assert await manager.get_room_user_count(activity_id) == 0


@pytest.mark.asyncio
async def test_connection_manager_broadcast_success() -> None:
    from app.core.ws_manager import ConnectionManager
    from app.schemas.chat import WebSocketEnvelope, WebSocketSystemData

    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    activity_id = "activity_1"

    await manager.connect(ws1, activity_id, 1)
    await manager.connect(ws2, activity_id, 2)

    envelope = WebSocketEnvelope(
        event="system", data=WebSocketSystemData(content="Hello", type="join")
    )

    await manager.broadcast_to_room(activity_id, envelope)

    expected_json = envelope.model_dump_json()
    ws1.send_text.assert_called_once_with(expected_json)
    ws2.send_text.assert_called_once_with(expected_json)


@pytest.mark.asyncio
async def test_connection_manager_broadcast_failure_cleanup() -> None:
    from app.core.ws_manager import ConnectionManager
    from app.schemas.chat import WebSocketEnvelope, WebSocketSystemData

    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    activity_id = "activity_1"

    ws1.send_text.side_effect = RuntimeError("Network error")

    await manager.connect(ws1, activity_id, 1)
    await manager.connect(ws2, activity_id, 2)

    envelope = WebSocketEnvelope(
        event="system", data=WebSocketSystemData(content="Hello", type="join")
    )

    await manager.broadcast_to_room(activity_id, envelope)

    assert await manager.get_room_connection_count(activity_id) == 1
    assert await manager.get_room_user_count(activity_id) == 1
    ws1.send_text.assert_called_once()
    ws2.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_connection_manager_disconnect_user() -> None:
    from app.core.ws_manager import ConnectionManager

    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws3 = AsyncMock()
    activity_id = "activity_1"

    await manager.connect(ws1, activity_id, 1)
    await manager.connect(ws2, activity_id, 1)
    await manager.connect(ws3, activity_id, 2)

    assert await manager.get_room_connection_count(activity_id) == 3
    assert await manager.get_room_user_count(activity_id) == 2

    await manager.disconnect_user(activity_id, 1, code=4003, reason="Kicked")

    ws1.close.assert_called_once_with(code=4003, reason="Kicked")
    ws2.close.assert_called_once_with(code=4003, reason="Kicked")
    ws3.close.assert_not_called()

    assert await manager.get_room_connection_count(activity_id) == 1
    assert await manager.get_room_user_count(activity_id) == 1


@pytest.mark.asyncio
async def test_rate_limiter_messages_within_limit() -> None:
    from app.core.ws_rate_limit import ChatRateLimiter

    limiter = ChatRateLimiter()
    activity_id = "activity_1"
    user_id = 1

    for _ in range(5):
        assert await limiter.check_rate_limit(activity_id, user_id) is True

    assert await limiter.get_violation_count(activity_id, user_id) == 0


@pytest.mark.asyncio
async def test_rate_limiter_rejects_sixth_message() -> None:
    from app.core.ws_rate_limit import ChatRateLimiter

    limiter = ChatRateLimiter()
    activity_id = "activity_1"
    user_id = 1

    for _ in range(5):
        assert await limiter.check_rate_limit(activity_id, user_id) is True

    assert await limiter.check_rate_limit(activity_id, user_id) is False
    assert await limiter.get_violation_count(activity_id, user_id) == 1


@pytest.mark.asyncio
async def test_rate_limiter_violation_count_increments_and_resets() -> None:
    from app.core.ws_rate_limit import ChatRateLimiter

    limiter = ChatRateLimiter()
    activity_id = "activity_1"
    user_id = 1

    for _ in range(5):
        await limiter.check_rate_limit(activity_id, user_id)

    await limiter.check_rate_limit(activity_id, user_id)
    assert await limiter.get_violation_count(activity_id, user_id) == 1

    await limiter.check_rate_limit(activity_id, user_id)
    assert await limiter.get_violation_count(activity_id, user_id) == 2

    await limiter.check_rate_limit(activity_id, user_id)
    assert await limiter.get_violation_count(activity_id, user_id) == 3

    with patch("app.core.ws_rate_limit.time") as mock_time:
        mock_time.monotonic.return_value = 1_000_000.0
        assert await limiter.check_rate_limit(activity_id, user_id) is True
        assert await limiter.get_violation_count(activity_id, user_id) == 0


@pytest.mark.asyncio
async def test_rate_limiter_allows_after_window_expires() -> None:
    from app.core.ws_rate_limit import ChatRateLimiter

    limiter = ChatRateLimiter()
    activity_id = "activity_1"
    user_id = 1

    base_time = 100.0

    with patch("app.core.ws_rate_limit.time") as mock_time:
        mock_time.monotonic.return_value = base_time
        for _ in range(5):
            await limiter.check_rate_limit(activity_id, user_id)

        assert await limiter.check_rate_limit(activity_id, user_id) is False

        mock_time.monotonic.return_value = base_time + 11.0
        assert await limiter.check_rate_limit(activity_id, user_id) is True
        assert await limiter.get_violation_count(activity_id, user_id) == 0


@pytest.mark.asyncio
async def test_rate_limiter_cleanup_user() -> None:
    from app.core.ws_rate_limit import ChatRateLimiter

    limiter = ChatRateLimiter()
    activity_id = "activity_1"
    user_id = 1

    for _ in range(5):
        await limiter.check_rate_limit(activity_id, user_id)

    await limiter.check_rate_limit(activity_id, user_id)
    assert await limiter.get_violation_count(activity_id, user_id) == 1

    await limiter.cleanup_user(activity_id, user_id)

    assert await limiter.get_violation_count(activity_id, user_id) == 0
    assert await limiter.check_rate_limit(activity_id, user_id) is True


@pytest.mark.asyncio
async def test_rate_limiter_max_violations_threshold() -> None:
    from app.core.ws_rate_limit import ChatRateLimiter, MAX_VIOLATIONS_BEFORE_DISCONNECT

    limiter = ChatRateLimiter()
    activity_id = "activity_1"
    user_id = 1

    for _ in range(5):
        await limiter.check_rate_limit(activity_id, user_id)

    for violation_number in range(1, MAX_VIOLATIONS_BEFORE_DISCONNECT + 1):
        await limiter.check_rate_limit(activity_id, user_id)
        assert (
            await limiter.get_violation_count(activity_id, user_id) == violation_number
        )

    assert (
        await limiter.get_violation_count(activity_id, user_id)
        >= MAX_VIOLATIONS_BEFORE_DISCONNECT
    )


@pytest.mark.asyncio
async def test_rate_limiter_independent_per_user_and_activity() -> None:
    from app.core.ws_rate_limit import ChatRateLimiter

    limiter = ChatRateLimiter()

    for _ in range(5):
        await limiter.check_rate_limit("activity_1", 1)

    assert await limiter.check_rate_limit("activity_1", 1) is False
    assert await limiter.check_rate_limit("activity_1", 2) is True
    assert await limiter.check_rate_limit("activity_2", 1) is True


@pytest.mark.asyncio
async def test_websocket_rate_limiter_concurrency() -> None:
    import asyncio
    from app.core.ws_rate_limit import ChatRateLimiter

    limiter = ChatRateLimiter()
    tasks = [limiter.check_rate_limit("activity_1", 1) for _ in range(10)]
    results = await asyncio.gather(*tasks)

    successes = results.count(True)
    failures = results.count(False)

    assert successes == 5
    assert failures == 5


def test_websocket_auth_failure() -> None:
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from fastapi import WebSocket
    from app.main import app
    from app.core.dependencies import get_current_user_ws

    async def mock_get_current_user_ws_fail(websocket: WebSocket, db=None) -> None:
        from fastapi import WebSocketException

        raise WebSocketException(code=4001, reason="Token missing")

    app.dependency_overrides.clear()
    from app.core.mongo import (
        get_activities_collection,
        get_membership_collection,
        get_chat_messages_collection,
    )
    from app.core.database import get_db
    from app.core.storage import get_s3_public_sign_client

    app.dependency_overrides[get_current_user_ws] = mock_get_current_user_ws_fail
    app.dependency_overrides[get_activities_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_membership_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_s3_public_sign_client] = lambda: MagicMock()

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/activities/any_id/chat") as websocket:
            websocket.receive_text()
    assert exc.value.code == 4001

    app.dependency_overrides.clear()


def test_websocket_missing_activity(mock_user: User) -> None:
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from app.main import app
    from app.core.mongo import get_activities_collection

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = None

    app.dependency_overrides.clear()
    from app.core.dependencies import get_current_user_ws
    from app.core.mongo import get_membership_collection, get_chat_messages_collection
    from app.core.database import get_db
    from app.core.storage import get_s3_public_sign_client

    app.dependency_overrides[get_current_user_ws] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_s3_public_sign_client] = lambda: MagicMock()

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/activities/507f1f77bcf86cd799439011/chat?token=valid"
        ):
            pass
    assert exc.value.code == 4004

    app.dependency_overrides.clear()


def test_websocket_non_member(mock_user: User) -> None:
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from app.main import app
    from app.core.mongo import get_activities_collection, get_membership_collection

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "status": "active",
    }

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = None

    app.dependency_overrides.clear()
    from app.core.dependencies import get_current_user_ws
    from app.core.mongo import get_chat_messages_collection
    from app.core.database import get_db
    from app.core.storage import get_s3_public_sign_client

    app.dependency_overrides[get_current_user_ws] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_s3_public_sign_client] = lambda: MagicMock()

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/activities/507f1f77bcf86cd799439011/chat?token=valid"
        ):
            pass
    assert exc.value.code == 4003

    app.dependency_overrides.clear()


def test_websocket_connection_success(mock_user: User) -> None:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.mongo import get_activities_collection, get_membership_collection

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "status": "active",
    }

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = {
        "activity_id": ObjectId("507f1f77bcf86cd799439011"),
        "user_id": mock_user.id,
        "status": "approved",
    }

    app.dependency_overrides.clear()
    from app.core.dependencies import get_current_user_ws
    from app.core.mongo import get_chat_messages_collection
    from app.core.database import get_db
    from app.core.storage import get_s3_public_sign_client

    app.dependency_overrides[get_current_user_ws] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_s3_public_sign_client] = lambda: MagicMock()

    client = TestClient(app)
    with client.websocket_connect(
        "/activities/507f1f77bcf86cd799439011/chat?token=valid"
    ) as websocket:
        data = websocket.receive_json()
        assert data["event"] == "system"
        assert data["data"]["content"] == f"{mock_user.username} joined the chat"
        assert data["data"]["type"] == "join"

        count_data = websocket.receive_json()
        assert count_data["event"] == "member_count"
        assert count_data["data"]["online_count"] == 1

    app.dependency_overrides.clear()


def test_websocket_send_valid_message(mock_user: User) -> None:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.database import get_db
    from app.core.dependencies import get_current_user_ws
    from app.core.mongo import (
        get_activities_collection,
        get_membership_collection,
        get_chat_messages_collection,
    )
    from app.core.storage import get_s3_public_sign_client

    app.dependency_overrides[get_current_user_ws] = lambda: mock_user

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "status": "active",
    }
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = {
        "activity_id": ObjectId("507f1f77bcf86cd799439011"),
        "user_id": mock_user.id,
        "status": "approved",
    }
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col

    mock_chat_col = AsyncMock()
    app.dependency_overrides[get_chat_messages_collection] = lambda: mock_chat_col

    mock_db = AsyncMock()
    mock_db.get.return_value = mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    mock_s3_sign = MagicMock()
    mock_s3_sign.generate_presigned_url.return_value = "http://fake-s3/avatar.jpg"
    app.dependency_overrides[get_s3_public_sign_client] = lambda: mock_s3_sign

    client = TestClient(app)
    with client.websocket_connect(
        "/activities/507f1f77bcf86cd799439011/chat?token=valid"
    ) as websocket:
        join_msg = websocket.receive_json()
        assert join_msg["event"] == "system"
        assert join_msg["data"]["type"] == "join"

        count_msg = websocket.receive_json()
        assert count_msg["event"] == "member_count"

        payload = {"event": "message", "data": {"content": "Hello hangout!"}}
        websocket.send_json(payload)

        broadcast_msg = websocket.receive_json()
        assert broadcast_msg["event"] == "message"
        assert broadcast_msg["data"]["content"] == "Hello hangout!"
        assert broadcast_msg["data"]["username"] == mock_user.username

    app.dependency_overrides.clear()


def test_websocket_send_invalid_json(mock_user: User) -> None:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.mongo import get_activities_collection, get_membership_collection

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "status": "active",
    }

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = {
        "activity_id": ObjectId("507f1f77bcf86cd799439011"),
        "user_id": mock_user.id,
        "status": "approved",
    }

    app.dependency_overrides.clear()
    from app.core.dependencies import get_current_user_ws
    from app.core.mongo import get_chat_messages_collection
    from app.core.database import get_db
    from app.core.storage import get_s3_public_sign_client

    app.dependency_overrides[get_current_user_ws] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_s3_public_sign_client] = lambda: MagicMock()

    client = TestClient(app)
    with client.websocket_connect(
        "/activities/507f1f77bcf86cd799439011/chat?token=valid"
    ) as websocket:
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_text("not a valid json")

        error_msg = websocket.receive_json()
        assert error_msg["event"] == "error"
        assert error_msg["data"]["detail"] == "Invalid JSON format"

        websocket.send_text('{"event": "non_existent"}')
        unknown_event_msg = websocket.receive_json()
        assert unknown_event_msg["event"] == "error"
        assert "Unknown event" in unknown_event_msg["data"]["detail"]

    app.dependency_overrides.clear()


def test_websocket_send_empty_or_oversized_message(mock_user: User) -> None:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.mongo import get_activities_collection, get_membership_collection

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "status": "active",
    }

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = {
        "activity_id": ObjectId("507f1f77bcf86cd799439011"),
        "user_id": mock_user.id,
        "status": "approved",
    }

    app.dependency_overrides.clear()
    from app.core.dependencies import get_current_user_ws
    from app.core.mongo import get_chat_messages_collection
    from app.core.database import get_db
    from app.core.storage import get_s3_public_sign_client

    app.dependency_overrides[get_current_user_ws] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_s3_public_sign_client] = lambda: MagicMock()

    client = TestClient(app)
    with client.websocket_connect(
        "/activities/507f1f77bcf86cd799439011/chat?token=valid"
    ) as websocket:
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_json({"event": "message", "data": {"content": "   "}})
        err1 = websocket.receive_json()
        assert err1["event"] == "error"
        assert err1["data"]["detail"] == "String should have at least 1 character"

        websocket.send_json({"event": "message", "data": {"content": "a" * 2001}})
        err2 = websocket.receive_json()
        assert err2["event"] == "error"
        assert err2["data"]["detail"] == "String should have at most 2000 characters"

        websocket.send_json({"event": "message", "data": {}})
        err3 = websocket.receive_json()
        assert err3["event"] == "error"
        assert err3["data"]["detail"] == "Field required"

    app.dependency_overrides.clear()


def test_websocket_client_cannot_create_system_messages(mock_user: User) -> None:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.mongo import get_activities_collection, get_membership_collection

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "status": "active",
    }

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = {
        "activity_id": ObjectId("507f1f77bcf86cd799439011"),
        "user_id": mock_user.id,
        "status": "approved",
    }

    mock_chat_col = AsyncMock()

    app.dependency_overrides.clear()
    from app.core.dependencies import get_current_user_ws
    from app.core.mongo import get_chat_messages_collection
    from app.core.database import get_db
    from app.core.storage import get_s3_public_sign_client

    app.dependency_overrides[get_current_user_ws] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: mock_chat_col
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_s3_public_sign_client] = lambda: MagicMock()

    client = TestClient(app)
    with client.websocket_connect(
        "/activities/507f1f77bcf86cd799439011/chat?token=valid"
    ) as websocket:
        # Drain initial join and member count broadcast envelopes
        websocket.receive_json()
        websocket.receive_json()

        # Send a message with the extra field "message_type": "system"
        websocket.send_json(
            {
                "event": "message",
                "data": {
                    "content": "I am system",
                    "message_type": "system",
                },
            }
        )
        err = websocket.receive_json()
        assert err["event"] == "error"
        assert err["data"]["detail"] == "Extra inputs are not permitted"

        # Verify that no insert/save was performed to MongoDB
        mock_chat_col.insert_one.assert_not_called()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_websocket_rate_limiting_disconnect(mock_user: User) -> None:
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from app.main import app
    from app.core.database import get_db
    from app.core.mongo import (
        get_activities_collection,
        get_membership_collection,
        get_chat_messages_collection,
    )
    from app.core.storage import get_s3_public_sign_client
    from app.core.ws_rate_limit import chat_rate_limiter

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "status": "active",
    }

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = {
        "activity_id": ObjectId("507f1f77bcf86cd799439011"),
        "user_id": mock_user.id,
        "status": "approved",
    }

    activity_id = "507f1f77bcf86cd799439011"
    await chat_rate_limiter.cleanup_user(activity_id, mock_user.id)

    mock_chat_col = AsyncMock()
    mock_db = AsyncMock()
    mock_db.get.return_value = mock_user
    mock_s3_sign = MagicMock()
    mock_s3_sign.generate_presigned_url.return_value = "http://fake-s3/avatar.jpg"

    app.dependency_overrides.clear()
    from app.core.dependencies import get_current_user_ws

    app.dependency_overrides[get_current_user_ws] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: mock_chat_col
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_s3_public_sign_client] = lambda: mock_s3_sign

    client = TestClient(app)
    with client.websocket_connect(
        f"/activities/{activity_id}/chat?token=valid"
    ) as websocket:
        websocket.receive_json()
        websocket.receive_json()

        for i in range(5):
            websocket.send_json({"event": "message", "data": {"content": f"msg {i}"}})
            assert websocket.receive_json()["event"] == "message"

        websocket.send_json({"event": "message", "data": {"content": "msg 6"}})
        err1 = websocket.receive_json()
        assert err1["event"] == "error"
        assert err1["data"]["detail"] == "Rate limit exceeded. Please wait."

        websocket.send_json({"event": "message", "data": {"content": "msg 7"}})
        err2 = websocket.receive_json()
        assert err2["event"] == "error"
        assert err2["data"]["detail"] == "Rate limit exceeded. Please wait."

        with pytest.raises(WebSocketDisconnect) as exc:
            websocket.send_json({"event": "message", "data": {"content": "msg 8"}})
            websocket.receive_json()
        assert exc.value.code == 4008

    app.dependency_overrides.clear()


def test_websocket_disconnect_leave_broadcast(mock_user: User) -> None:
    from fastapi.testclient import TestClient
    from fastapi import WebSocket, WebSocketException
    from app.main import app
    from app.core.dependencies import get_current_user_ws
    from app.core.mongo import get_activities_collection, get_membership_collection

    user_a = mock_user
    user_b = User(
        id=2,
        email="user_b@user.com",
        username="user_b",
        is_active=True,
        password="hashed_password",
        avatar=None,
        created_at=user_a.created_at,
    )

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "status": "active",
    }

    async def mock_get_current_user_ws(websocket: WebSocket, db=None) -> User:
        token = websocket.query_params.get("token")
        if token == "token_a":
            return user_a
        elif token == "token_b":
            return user_b
        raise WebSocketException(code=4001, reason="Invalid token")

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.side_effect = lambda query: {
        "activity_id": ObjectId("507f1f77bcf86cd799439011"),
        "user_id": query["user_id"],
        "status": "approved",
    }

    app.dependency_overrides.clear()
    from app.core.mongo import get_chat_messages_collection
    from app.core.database import get_db
    from app.core.storage import get_s3_public_sign_client

    app.dependency_overrides[get_current_user_ws] = mock_get_current_user_ws
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_s3_public_sign_client] = lambda: MagicMock()

    client = TestClient(app)

    with client.websocket_connect(
        "/activities/507f1f77bcf86cd799439011/chat?token=token_b"
    ) as ws_b:
        join_b = ws_b.receive_json()
        assert join_b["event"] == "system"
        assert join_b["data"]["type"] == "join"
        count_b = ws_b.receive_json()
        assert count_b["event"] == "member_count"
        assert count_b["data"]["online_count"] == 1

        with client.websocket_connect(
            "/activities/507f1f77bcf86cd799439011/chat?token=token_a"
        ) as ws_a:
            join_a_own = ws_a.receive_json()
            assert join_a_own["event"] == "system"
            assert join_a_own["data"]["type"] == "join"
            count_a_own = ws_a.receive_json()
            assert count_a_own["event"] == "member_count"
            assert count_a_own["data"]["online_count"] == 2

            join_a = ws_b.receive_json()
            assert join_a["event"] == "system"
            assert join_a["data"]["type"] == "join"
            assert join_a["data"]["content"] == "testuser joined the chat"

            count_b_2 = ws_b.receive_json()
            assert count_b_2["event"] == "member_count"
            assert count_b_2["data"]["online_count"] == 2

        leave_a = ws_b.receive_json()
        assert leave_a["event"] == "system"
        assert leave_a["data"]["type"] == "leave"
        assert leave_a["data"]["content"] == "testuser left the chat"

        count_b_after = ws_b.receive_json()
        assert count_b_after["event"] == "member_count"
        assert count_b_after["data"]["online_count"] == 1

    app.dependency_overrides.clear()


def test_websocket_member_count_scenarios(mock_user: User) -> None:
    from fastapi.testclient import TestClient
    from fastapi import WebSocket, WebSocketException
    from app.main import app
    from app.core.dependencies import get_current_user_ws
    from app.core.mongo import get_activities_collection, get_membership_collection

    user_a = mock_user
    user_b = User(
        id=2,
        email="user_b@user.com",
        username="user_b",
        is_active=True,
        password="hashed_password",
        avatar=None,
        created_at=user_a.created_at,
    )

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "status": "active",
    }

    async def mock_get_current_user_ws(websocket: WebSocket, db=None) -> User:
        token = websocket.query_params.get("token")
        if token == "token_a":
            return user_a
        elif token == "token_b":
            return user_b
        raise WebSocketException(code=4001, reason="Invalid token")

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.side_effect = lambda query: {
        "activity_id": ObjectId("507f1f77bcf86cd799439011"),
        "user_id": query["user_id"],
        "status": "approved",
    }

    app.dependency_overrides.clear()
    from app.core.mongo import get_chat_messages_collection
    from app.core.database import get_db
    from app.core.storage import get_s3_public_sign_client

    app.dependency_overrides[get_current_user_ws] = mock_get_current_user_ws
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_s3_public_sign_client] = lambda: MagicMock()

    client = TestClient(app)

    # 1. Connect user A (Tab 1) -> online_count should be 1
    with client.websocket_connect(
        "/activities/507f1f77bcf86cd799439011/chat?token=token_a"
    ) as ws_a1:
        join_a1 = ws_a1.receive_json()
        assert join_a1["event"] == "system"
        assert join_a1["data"]["type"] == "join"

        count_a1 = ws_a1.receive_json()
        assert count_a1["event"] == "member_count"
        assert count_a1["data"]["online_count"] == 1

        # 2. Connect user A again (Tab 2) -> online_count should still be 1 (same user)
        with client.websocket_connect(
            "/activities/507f1f77bcf86cd799439011/chat?token=token_a"
        ) as ws_a2:
            # ws_a2 (Tab 2) gets join and member_count = 1
            join_a2 = ws_a2.receive_json()
            assert join_a2["event"] == "system"
            assert join_a2["data"]["type"] == "join"
            count_a2 = ws_a2.receive_json()
            assert count_a2["event"] == "member_count"
            assert count_a2["data"]["online_count"] == 1

            # ws_a1 (Tab 1) gets the join and member_count = 1 from Tab 2
            join_a1_dup = ws_a1.receive_json()
            assert join_a1_dup["event"] == "system"
            assert join_a1_dup["data"]["type"] == "join"
            count_a1_dup = ws_a1.receive_json()
            assert count_a1_dup["event"] == "member_count"
            assert count_a1_dup["data"]["online_count"] == 1

            # 3. Connect user B -> online_count should be 2
            with client.websocket_connect(
                "/activities/507f1f77bcf86cd799439011/chat?token=token_b"
            ) as ws_b:
                # ws_b gets join and member_count = 2
                join_b = ws_b.receive_json()
                assert join_b["event"] == "system"
                assert join_b["data"]["type"] == "join"
                count_b = ws_b.receive_json()
                assert count_b["event"] == "member_count"
                assert count_b["data"]["online_count"] == 2

                # ws_a1 (Tab 1) and ws_a2 (Tab 2) both receive B's join and member_count = 2
                join_a1_recv = ws_a1.receive_json()
                assert join_a1_recv["event"] == "system"
                assert join_a1_recv["data"]["type"] == "join"
                count_a1_b = ws_a1.receive_json()
                assert count_a1_b["event"] == "member_count"
                assert count_a1_b["data"]["online_count"] == 2

                join_a2_recv = ws_a2.receive_json()
                assert join_a2_recv["event"] == "system"
                assert join_a2_recv["data"]["type"] == "join"
                count_a2_b = ws_a2.receive_json()
                assert count_a2_b["event"] == "member_count"
                assert count_a2_b["data"]["online_count"] == 2

            # User B disconnects -> online_count back to 1
            # ws_a1 and ws_a2 receive leave and then member_count = 1
            leave_a1 = ws_a1.receive_json()
            assert leave_a1["event"] == "system"
            assert leave_a1["data"]["type"] == "leave"
            c_a1 = ws_a1.receive_json()
            assert c_a1["event"] == "member_count"

            leave_a2 = ws_a2.receive_json()
            assert leave_a2["event"] == "system"
            assert leave_a2["data"]["type"] == "leave"
            c_a2 = ws_a2.receive_json()
            assert c_a2["event"] == "member_count"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_websocket_multi_tab_rate_limiter_cleanup(mock_user: User) -> None:
    from fastapi.testclient import TestClient
    from fastapi import WebSocket
    from app.main import app
    from app.core.dependencies import get_current_user_ws
    from app.core.mongo import get_activities_collection, get_membership_collection
    from app.core.ws_rate_limit import chat_rate_limiter
    from bson import ObjectId
    from unittest.mock import AsyncMock, MagicMock

    user_a = mock_user

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "status": "active",
    }

    async def mock_get_current_user_ws(websocket: WebSocket, db=None) -> User:
        return user_a

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = {
        "activity_id": ObjectId("507f1f77bcf86cd799439011"),
        "user_id": user_a.id,
        "status": "approved",
    }

    app.dependency_overrides.clear()
    from app.core.mongo import get_chat_messages_collection
    from app.core.database import get_db
    from app.core.storage import get_s3_public_sign_client

    mock_db = AsyncMock()
    mock_db.get.return_value = user_a

    mock_s3_sign = MagicMock()
    mock_s3_sign.generate_presigned_url.return_value = "http://fake-s3/avatar.jpg"

    app.dependency_overrides[get_current_user_ws] = mock_get_current_user_ws
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_s3_public_sign_client] = lambda: mock_s3_sign

    client = TestClient(app)
    activity_id = "507f1f77bcf86cd799439011"

    # Make sure rate limiter is clean for this test
    await chat_rate_limiter.cleanup_user(activity_id, user_a.id)

    # Connect User A (Tab 1)
    with client.websocket_connect(
        f"/activities/{activity_id}/chat?token=token_a"
    ) as ws_a1:
        ws_a1.receive_json()
        ws_a1.receive_json()

        # Connect User A again (Tab 2)
        with client.websocket_connect(
            f"/activities/{activity_id}/chat?token=token_a"
        ) as ws_a2:
            ws_a2.receive_json()
            ws_a2.receive_json()

            ws_a1.receive_json()
            ws_a1.receive_json()

            # Send 5 messages from User A (Tab 1) to saturate the rate limit window.
            # Verify a 6th message is rate limited.
            for i in range(5):
                ws_a1.send_json({"event": "message", "data": {"content": f"msg {i}"}})
                assert ws_a1.receive_json()["event"] == "message"
                assert ws_a2.receive_json()["event"] == "message"

            ws_a1.send_json({"event": "message", "data": {"content": "msg 6"}})
            err = ws_a1.receive_json()
            assert err["event"] == "error"
            assert err["data"]["detail"] == "Rate limit exceeded. Please wait."

        # Disconnect User A (Tab 2) (closes one tab) by exiting the inner context.
        # Consume the leave and member_count events on ws_a1
        ws_a1.receive_json()  # leave
        ws_a1.receive_json()  # member_count

        # Verify that the rate limiter is NOT cleaned up for User A because Tab 1 is still connected.
        # A message sent from Tab 1 should still be rate limited.
        ws_a1.send_json({"event": "message", "data": {"content": "msg 7"}})
        err = ws_a1.receive_json()
        assert err["event"] == "error"
        assert err["data"]["detail"] == "Rate limit exceeded. Please wait."

    # Disconnect User A (Tab 1) (closes the last tab) by exiting the outer context.
    # Verify that the rate limiter is now cleaned up (connecting again should immediately allow messages).
    with client.websocket_connect(
        f"/activities/{activity_id}/chat?token=token_a"
    ) as ws_a3:
        ws_a3.receive_json()
        ws_a3.receive_json()

        ws_a3.send_json({"event": "message", "data": {"content": "fresh start msg"}})
        msg = ws_a3.receive_json()
        assert msg["event"] == "message"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_chat_history_success(async_client, mock_user) -> None:
    from app.core.dependencies import get_current_user
    from app.core.mongo import (
        get_activities_collection,
        get_membership_collection,
        get_chat_messages_collection,
    )
    from app.main import app

    activity_id = str(ObjectId())

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId(activity_id),
        "status": "active",
    }

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = {
        "activity_id": ObjectId(activity_id),
        "user_id": mock_user.id,
        "status": "approved",
    }

    msg_id1 = ObjectId()
    msg_id2 = ObjectId()
    mock_chat_col = AsyncMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": msg_id1,
                "activity_id": ObjectId(activity_id),
                "user_id": mock_user.id,
                "username": mock_user.username,
                "avatar_url": None,
                "content": "hello 1",
                "message_type": "text",
                "created_at": datetime.now(timezone.utc),
            },
            {
                "_id": msg_id2,
                "activity_id": ObjectId(activity_id),
                "user_id": mock_user.id,
                "username": mock_user.username,
                "avatar_url": None,
                "content": "hello 2",
                "message_type": "text",
                "created_at": datetime.now(timezone.utc),
            },
        ]
    )
    mock_chat_col.find = MagicMock(return_value=mock_cursor)

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: mock_chat_col

    try:
        response = await async_client.get(
            f"/activities/{activity_id}/chat/history?limit=1"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["content"] == "hello 1"
        assert data["has_more"] is True
        assert data["next_cursor"] == str(msg_id1)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_chat_history_not_member(async_client, mock_user) -> None:
    from app.core.dependencies import get_current_user
    from app.core.mongo import (
        get_activities_collection,
        get_membership_collection,
        get_chat_messages_collection,
    )
    from app.main import app

    activity_id = str(ObjectId())

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId(activity_id),
        "status": "active",
    }

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = None

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()

    try:
        response = await async_client.get(f"/activities/{activity_id}/chat/history")
        assert response.status_code == 403
        assert (
            response.json()["detail"]
            == "User is not an approved member of this activity"
        )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_chat_history_activity_not_found(async_client, mock_user) -> None:
    from app.core.dependencies import get_current_user
    from app.core.mongo import (
        get_activities_collection,
        get_membership_collection,
        get_chat_messages_collection,
    )
    from app.main import app

    activity_id = str(ObjectId())

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = None

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()

    try:
        response = await async_client.get(f"/activities/{activity_id}/chat/history")
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_chat_history_activity_not_active(async_client, mock_user) -> None:
    from app.core.dependencies import get_current_user
    from app.core.mongo import (
        get_activities_collection,
        get_membership_collection,
        get_chat_messages_collection,
    )
    from app.main import app

    activity_id = str(ObjectId())

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId(activity_id),
        "status": "completed",
    }

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()

    try:
        response = await async_client.get(f"/activities/{activity_id}/chat/history")
        assert response.status_code == 400
        assert response.json()["detail"] == "Activity is not active"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_chat_history_invalid_activity_id(async_client, mock_user) -> None:
    from app.core.dependencies import get_current_user
    from app.core.mongo import (
        get_activities_collection,
        get_membership_collection,
        get_chat_messages_collection,
    )
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_membership_collection] = lambda: AsyncMock()
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()

    try:
        response = await async_client.get("/activities/invalid_id/chat/history")
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid activity id"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_chat_history_invalid_cursor(async_client, mock_user) -> None:
    from app.core.dependencies import get_current_user
    from app.core.mongo import (
        get_activities_collection,
        get_membership_collection,
        get_chat_messages_collection,
    )
    from app.main import app

    activity_id = str(ObjectId())

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = {
        "_id": ObjectId(activity_id),
        "status": "active",
    }

    mock_membership_col = AsyncMock()
    mock_membership_col.find_one.return_value = {
        "activity_id": ObjectId(activity_id),
        "user_id": mock_user.id,
        "status": "approved",
    }

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_activities_collection] = lambda: mock_activities_col
    app.dependency_overrides[get_membership_collection] = lambda: mock_membership_col
    app.dependency_overrides[get_chat_messages_collection] = lambda: AsyncMock()

    try:
        response = await async_client.get(
            f"/activities/{activity_id}/chat/history?cursor=invalid_cursor"
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid cursor"
    finally:
        app.dependency_overrides.clear()
