from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.asynchronous.collection import AsyncCollection, ReturnDocument
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User, UserRole
from app.schemas.activity import (
    ActivityCreate,
    ActivityResponse,
    ActivityStatus,
    ActivityResponseFeed,
    ActivityUpdate,
)


class ActivityService:
    @staticmethod
    async def _get_activity_doc_or_404(
        activity_id: str, collection: AsyncCollection
    ) -> dict:
        if not ObjectId.is_valid(activity_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid activity id"
            )
        doc = await collection.find_one({"_id": ObjectId(activity_id)})
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found"
            )
        return doc

    @staticmethod
    def _check_manage_permission(activity_doc, current_user) -> None:
        if (
            not activity_doc["creator_id"] == current_user.id
            and not current_user.user_role == UserRole.moderator
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to this activity",
            )

    @staticmethod
    async def _fetch_users_map(user_ids: set[int], db: AsyncSession) -> dict[int, User]:
        if not user_ids:
            return {}

        result = await db.execute(
            select(User).where(
                User.id.in_(user_ids),
                User.is_active.is_(True),
            )
        )
        users = result.scalars().all()
        return {user.id: user for user in users}

    @staticmethod
    def _build_creator_preview(user: User | None, s3_public_sign) -> dict | None:
        if user is None:
            return None

        return {
            "id": user.id,
            "username": user.username,
            "avatar_key": ActivityService._normalize_image_key(user.avatar),
            "avatar_url": ActivityService._build_avatar_url(
                user.avatar, s3_public_sign
            ),
        }

    @staticmethod
    async def _to_activity_response(
        doc: dict, db: AsyncSession, s3_public_sign
    ) -> ActivityResponse:
        users_map = await ActivityService._fetch_users_map({doc["creator_id"]}, db)
        creator = ActivityService._build_creator_preview(
            users_map.get(doc["creator_id"]), s3_public_sign
        )

        return ActivityResponse(**doc, creator=creator)

    @staticmethod
    def _normalize_image_key(value: str | None) -> str | None:
        if value is None:
            return None

        return value

    @staticmethod
    def _build_avatar_url(avatar_key: str | None, s3_public_sign) -> str | None:
        if avatar_key is None:
            return None

        return s3_public_sign.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.BUCKET_NAME, "Key": avatar_key},
            ExpiresIn=settings.PRESIGNED_URL_EXPIRES_SECONDS,
        )

    @staticmethod
    async def create_activity(
        activity_data: ActivityCreate,
        creator_id: int,
        collection: AsyncCollection,
        db: AsyncSession,
        s3_public_sign,
    ) -> ActivityResponse:
        now = datetime.now(timezone.utc)

        activity_dict = activity_data.model_dump()
        activity_dict["creator_id"] = creator_id
        activity_dict["current_members"] = 1
        activity_dict["status"] = ActivityStatus.active.value
        activity_dict["created_at"] = now
        activity_dict["updated_at"] = now

        result = await collection.insert_one(activity_dict)
        created_activity = await collection.find_one({"_id": result.inserted_id})

        return await ActivityService._to_activity_response(
            created_activity, db, s3_public_sign
        )

    @staticmethod
    async def list_feed(
        collection: AsyncCollection,
        db: AsyncSession,
        s3_public_sign,
        limit: int = 10,
        cursor: str | None = None,
    ) -> ActivityResponseFeed:
        query: dict = {}

        if cursor:
            if not ObjectId.is_valid(cursor):
                raise HTTPException(status_code=400, detail="Invalid cursor")
            query["_id"] = {"$lt": ObjectId(cursor)}

        limit = max(1, min(limit, 50))

        docs = await (
            collection.find(query)
            .sort("_id", -1)
            .limit(limit + 1)
            .to_list(length=limit + 1)
        )

        has_more = len(docs) > limit
        items_docs = docs[:limit]
        next_cursor = str(items_docs[-1]["_id"]) if has_more and items_docs else None

        creator_ids = {doc["creator_id"] for doc in items_docs}
        users_map = await ActivityService._fetch_users_map(creator_ids, db)

        items: list[ActivityResponse] = []
        for doc in items_docs:
            creator = ActivityService._build_creator_preview(
                users_map.get(doc["creator_id"]), s3_public_sign
            )
            items.append(ActivityResponse(**doc, creator=creator))

        return ActivityResponseFeed(
            items=items, next_cursor=next_cursor, has_more=has_more
        )

    @staticmethod
    async def get_activity(
        activity_id: str, collection: AsyncCollection, db: AsyncSession, s3_public_sign
    ) -> ActivityResponse:
        doc = await ActivityService._get_activity_doc_or_404(activity_id, collection)

        return await ActivityService._to_activity_response(doc, db, s3_public_sign)

    @staticmethod
    async def update_activity(
        activity_id: str,
        data: ActivityUpdate,
        current_user: User,
        collection: AsyncCollection,
        db: AsyncSession,
        s3_public_sign,
    ) -> ActivityResponse:
        doc = await ActivityService._get_activity_doc_or_404(activity_id, collection)

        ActivityService._check_manage_permission(doc, current_user)

        update_data = data.model_dump(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update"
            )

        update_data["updated_at"] = datetime.now(timezone.utc)

        result = await collection.find_one_and_update(
            {"_id": ObjectId(activity_id)},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity not found after update",
            )

        return await ActivityService._to_activity_response(result, db, s3_public_sign)

    @staticmethod
    async def delete_activity(
        activity_id: str, current_user: User, collection: AsyncCollection
    ) -> None:
        doc = await ActivityService._get_activity_doc_or_404(activity_id, collection)
        ActivityService._check_manage_permission(doc, current_user)

        result = await collection.delete_one({"_id": ObjectId(activity_id)})

        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return 
