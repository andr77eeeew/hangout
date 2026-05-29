import json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from pymongo.asynchronous.collection import AsyncCollection
from sqlalchemy.ext.asyncio import AsyncSession
from botocore.client import BaseClient
from pydantic import ValidationError

from app.core.database import get_db
from app.core.dependencies import get_current_user_ws, get_current_user
from app.core.mongo import (
    get_activities_collection,
    get_membership_collection,
    get_chat_messages_collection,
)
from app.core.storage import get_s3_public_sign_client
from app.core.ws_manager import connection_manager
from app.core.ws_rate_limit import chat_rate_limiter, MAX_VIOLATIONS_BEFORE_DISCONNECT
from app.models.user import User
from app.schemas.chat import (
    ClientChatMessage,
    WebSocketEnvelope,
    WebSocketSystemData,
    WebSocketErrorData,
    ChatHistoryResponse,
    WebSocketMemberCountData,
    WebSocketEvent,
    SystemEventType,
)
from app.services.chat import ChatService

router = APIRouter(prefix="/activities", tags=["💬 Chat"])


@router.get("/{activity_id}/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    activity_id: str,
    limit: int = 50,
    cursor: str | None = None,
    current_user: User = Depends(get_current_user),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
    chat_col: AsyncCollection = Depends(get_chat_messages_collection),
) -> ChatHistoryResponse:
    await ChatService.verify_chat_access(
        user_id=current_user.id,
        activity_id=activity_id,
        activities_col=activities_col,
        membership_col=membership_col,
    )
    return await ChatService.get_history(
        activity_id=activity_id,
        chat_col=chat_col,
        limit=limit,
        cursor=cursor,
    )


@router.websocket("/{activity_id}/chat")
async def websocket_chat(
    websocket: WebSocket,
    activity_id: str,
    user: User = Depends(get_current_user_ws),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
    chat_col: AsyncCollection = Depends(get_chat_messages_collection),
    db: AsyncSession = Depends(get_db),
    s3_public_sign: BaseClient = Depends(get_s3_public_sign_client),
) -> None:
    try:
        await ChatService.verify_chat_access(
            user_id=user.id,
            activity_id=activity_id,
            activities_col=activities_col,
            membership_col=membership_col,
        )
    except HTTPException as e:
        if e.status_code in (404, 400):
            await websocket.close(code=4004)
        elif e.status_code == 403:
            await websocket.close(code=4003)
        else:
            await websocket.close(code=4000)
        return

    await websocket.accept()
    await connection_manager.connect(websocket, activity_id, user.id)

    join_envelope = WebSocketEnvelope(
        event=WebSocketEvent.system,
        data=WebSocketSystemData(
            content=f"{user.username} joined the chat", type=SystemEventType.join
        ),
    )
    await connection_manager.broadcast_to_room(activity_id, join_envelope)

    online_count = await connection_manager.get_room_user_count(activity_id)
    count_envelope = WebSocketEnvelope(
        event=WebSocketEvent.member_count,
        data=WebSocketMemberCountData(online_count=online_count),
    )
    await connection_manager.broadcast_to_room(activity_id, count_envelope)

    try:
        while True:
            data_str = await websocket.receive_text()
            try:
                payload = json.loads(data_str)
            except json.JSONDecodeError:
                error_envelope = WebSocketEnvelope(
                    event=WebSocketEvent.error,
                    data=WebSocketErrorData(detail="Invalid JSON format"),
                )
                await websocket.send_text(error_envelope.model_dump_json())
                continue

            if not isinstance(payload, dict):
                error_envelope = WebSocketEnvelope(
                    event=WebSocketEvent.error,
                    data=WebSocketErrorData(detail="Invalid message format"),
                )
                await websocket.send_text(error_envelope.model_dump_json())
                continue

            event = payload.get("event")
            if event != "message":
                error_envelope = WebSocketEnvelope(
                    event=WebSocketEvent.error,
                    data=WebSocketErrorData(detail=f"Unknown event: {event}"),
                )
                await websocket.send_text(error_envelope.model_dump_json())
                continue

            data = payload.get("data")
            if not isinstance(data, dict):
                error_envelope = WebSocketEnvelope(
                    event=WebSocketEvent.error,
                    data=WebSocketErrorData(detail="Invalid message format"),
                )
                await websocket.send_text(error_envelope.model_dump_json())
                continue

            try:
                client_msg = ClientChatMessage(**data)
                content = client_msg.content
            except ValidationError as e:
                # Extract a clean validation error message from Pydantic
                error_detail = e.errors()[0]["msg"]
                error_envelope = WebSocketEnvelope(
                    event=WebSocketEvent.error,
                    data=WebSocketErrorData(detail=error_detail),
                )
                await websocket.send_text(error_envelope.model_dump_json())
                continue

            if not await chat_rate_limiter.check_rate_limit(activity_id, user.id):
                violations = await chat_rate_limiter.get_violation_count(
                    activity_id, user.id
                )
                if violations >= MAX_VIOLATIONS_BEFORE_DISCONNECT:
                    await websocket.close(code=4008)
                    break
                else:
                    error_envelope = WebSocketEnvelope(
                        event=WebSocketEvent.error,
                        data=WebSocketErrorData(
                            detail="Rate limit exceeded. Please wait."
                        ),
                    )
                    await websocket.send_text(error_envelope.model_dump_json())
                    continue

            saved_msg = await ChatService.save_message(
                user_id=user.id,
                activity_id=activity_id,
                content=content,
                chat_col=chat_col,
                db=db,
                s3_public_sign=s3_public_sign,
            )
            msg_envelope = WebSocketEnvelope(
                event=WebSocketEvent.message, data=saved_msg
            )
            await connection_manager.broadcast_to_room(activity_id, msg_envelope)

    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(websocket, activity_id, user.id)

        leave_envelope = WebSocketEnvelope(
            event=WebSocketEvent.system,
            data=WebSocketSystemData(
                content=f"{user.username} left the chat", type=SystemEventType.leave
            ),
        )
        await connection_manager.broadcast_to_room(activity_id, leave_envelope)

        online_count = await connection_manager.get_room_user_count(activity_id)
        count_envelope = WebSocketEnvelope(
            event=WebSocketEvent.member_count,
            data=WebSocketMemberCountData(online_count=online_count),
        )
        await connection_manager.broadcast_to_room(activity_id, count_envelope)

        if not await connection_manager.has_user_connections(activity_id, user.id):
            await chat_rate_limiter.cleanup_user(activity_id, user.id)
