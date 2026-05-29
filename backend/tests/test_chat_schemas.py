from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.chat import (
    ClientChatMessage,
    ChatMessageResponse,
    ChatHistoryResponse,
    WebSocketSystemData,
    WebSocketMemberCountData,
    WebSocketErrorData,
    WebSocketEnvelope,
    MessageType,
)


def test_client_chat_message_validation():
    # Standard valid message
    msg = ClientChatMessage(content="Hello World")
    assert msg.content == "Hello World"

    # Whitespace stripping
    msg_strip = ClientChatMessage(content="   Trim me   ")
    assert msg_strip.content == "Trim me"

    # Empty content (raises validation error due to min_length=1 after strip)
    with pytest.raises(ValidationError):
        ClientChatMessage(content="   ")

    # Content length > 2000
    with pytest.raises(ValidationError):
        ClientChatMessage(content="a" * 2001)


def test_chat_message_response_validation():
    data = {
        "_id": "60d5ec49c4f1c9a6f81a1b3a",
        "activity_id": "60d5ec49c4f1c9a6f81a1b3b",
        "user_id": 42,
        "username": "alice",
        "avatar_url": "https://example.com/avatar.png",
        "content": "Hello team!",
        "message_type": MessageType.text,
        "created_at": datetime(2026, 5, 28, 12, 0, 0),  # naive datetime
    }

    response = ChatMessageResponse(**data)
    assert response.id == "60d5ec49c4f1c9a6f81a1b3a"
    assert response.activity_id == "60d5ec49c4f1c9a6f81a1b3b"
    assert response.user_id == 42
    assert response.username == "alice"
    assert response.avatar_url == "https://example.com/avatar.png"
    assert response.content == "Hello team!"
    assert response.message_type == MessageType.text
    # Check timezone-aware conversion
    assert response.created_at.tzinfo == timezone.utc


def test_chat_history_response():
    data = {
        "_id": "60d5ec49c4f1c9a6f81a1b3a",
        "activity_id": "60d5ec49c4f1c9a6f81a1b3b",
        "user_id": 42,
        "username": "alice",
        "content": "Hello team!",
        "message_type": MessageType.text,
        "created_at": datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc),
    }
    history = ChatHistoryResponse(
        items=[ChatMessageResponse(**data)],
        next_cursor="60d5ec49c4f1c9a6f81a1b3a",
        has_more=True,
    )
    assert len(history.items) == 1
    assert history.next_cursor == "60d5ec49c4f1c9a6f81a1b3a"
    assert history.has_more is True


def test_websocket_envelope_with_chat_message():
    chat_data = {
        "_id": "60d5ec49c4f1c9a6f81a1b3a",
        "activity_id": "60d5ec49c4f1c9a6f81a1b3b",
        "user_id": 42,
        "username": "alice",
        "content": "Hello team!",
        "message_type": MessageType.text,
        "created_at": datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc),
    }
    envelope = WebSocketEnvelope(
        event="message",
        data=ChatMessageResponse(**chat_data),
    )
    assert envelope.event == "message"
    assert isinstance(envelope.data, ChatMessageResponse)
    assert envelope.data.content == "Hello team!"


def test_websocket_envelope_with_system_data():
    system_data = {
        "content": "User bob has joined.",
        "type": "join",
    }
    envelope = WebSocketEnvelope(
        event="system",
        data=WebSocketSystemData(**system_data),
    )
    assert envelope.event == "system"
    assert isinstance(envelope.data, WebSocketSystemData)
    assert envelope.data.type == "join"


def test_websocket_envelope_with_member_count():
    member_data = {
        "online_count": 5,
    }
    envelope = WebSocketEnvelope(
        event="presence",
        data=WebSocketMemberCountData(**member_data),
    )
    assert envelope.event == "presence"
    assert isinstance(envelope.data, WebSocketMemberCountData)
    assert envelope.data.online_count == 5


def test_websocket_envelope_with_error():
    error_data = {
        "detail": "Failed to connect",
    }
    envelope = WebSocketEnvelope(
        event="error",
        data=WebSocketErrorData(**error_data),
    )
    assert envelope.event == "error"
    assert isinstance(envelope.data, WebSocketErrorData)
    assert envelope.data.detail == "Failed to connect"
