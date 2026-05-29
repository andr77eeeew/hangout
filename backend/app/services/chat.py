from datetime import datetime, timezone

from bson import ObjectId
from botocore.client import BaseClient
from fastapi import HTTPException, status
from pymongo.asynchronous.collection import AsyncCollection
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.image_utils import build_image_url
from app.models.user import User
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatMessageResponse,
    MessageType,
)


class ChatService:
    @staticmethod
    async def verify_chat_access(
        user_id: int,
        activity_id: str,
        activities_col: AsyncCollection,
        membership_col: AsyncCollection,
    ) -> dict:
        if not ObjectId.is_valid(activity_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid activity id",
            )

        activity = await activities_col.find_one({"_id": ObjectId(activity_id)})
        if activity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity not found",
            )

        if activity.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity is not active",
            )

        membership = await membership_col.find_one(
            {
                "activity_id": ObjectId(activity_id),
                "user_id": user_id,
                "status": "approved",
            }
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not an approved member of this activity",
            )

        return activity

    @staticmethod
    async def save_message(
        user_id: int,
        activity_id: str,
        content: str,
        chat_col: AsyncCollection,
        db: AsyncSession,
        s3_public_sign: BaseClient | None = None,
    ) -> ChatMessageResponse:
        stripped_content = content.strip() if content else ""
        if not stripped_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message content cannot be empty",
            )

        if len(stripped_content) > 2000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message content is too long",
            )

        user = await db.get(User, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        avatar_url = (
            build_image_url(user.avatar, s3_public_sign) if user.avatar else None
        )

        msg_doc = {
            "_id": ObjectId(),
            "activity_id": ObjectId(activity_id),
            "user_id": user_id,
            "username": user.username,
            "avatar_url": avatar_url,
            "content": stripped_content,
            "message_type": MessageType.text.value,
            "created_at": datetime.now(timezone.utc),
        }

        await chat_col.insert_one(msg_doc)

        return ChatMessageResponse(**msg_doc)

    @staticmethod
    async def get_history(
        activity_id: str,
        chat_col: AsyncCollection,
        limit: int = 50,
        cursor: str | None = None,
    ) -> ChatHistoryResponse:
        if not ObjectId.is_valid(activity_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid activity id",
            )

        if cursor is not None and not ObjectId.is_valid(cursor):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor",
            )

        limit = min(max(1, limit), 100)
        query = {"activity_id": ObjectId(activity_id)}

        if cursor is not None:
            query["_id"] = {"$lt": ObjectId(cursor)}

        cursor_obj = chat_col.find(query).sort("_id", -1).limit(limit + 1)
        messages = await cursor_obj.to_list(length=limit + 1)

        has_more = len(messages) > limit
        if has_more:
            items_docs = messages[:limit]
            next_cursor = str(items_docs[-1]["_id"])
        else:
            items_docs = messages
            next_cursor = None

        return ChatHistoryResponse(
            items=[ChatMessageResponse(**msg) for msg in items_docs],
            next_cursor=next_cursor,
            has_more=has_more,
        )
