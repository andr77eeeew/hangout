from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.asynchronous.collection import AsyncCollection, ReturnDocument

from app.models.user import User
from app.schemas.activity import (
    ActivityCreate,
    ActivityResponse,
    ActivityStatus,
    ActivityResponseFeed,
    ActivityUpdate,
)


class ActivityService:
    @staticmethod
    async def create_activity(
        activity_data: ActivityCreate, creator_id: int, collection: AsyncCollection
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

        return ActivityResponse(**created_activity)

    @staticmethod
    async def list_feed(
        collection: AsyncCollection, limit: int = 10, cursor: str | None = None
    ) -> ActivityResponseFeed:

        query = {}
        if cursor:
            if ObjectId.is_valid(cursor):
                query["_id"] = {"$lt": ObjectId(cursor)}
            else:
                raise HTTPException(status_code=400, detail="Invalid cursor")

        if limit < 1:
            limit = 1
        elif limit > 50:
            limit = 50

        docs = (
            await collection.find(query)
            .sort("_id", -1)
            .limit(limit + 1)
            .to_list(length=limit + 1)
        )

        has_more = len(docs) > limit
        items_docs = docs[:limit]
        next_cursor = str(items_docs[-1]["_id"]) if has_more and items_docs else None

        items = [ActivityResponse(**doc) for doc in items_docs]
        return ActivityResponseFeed(
            items=items, next_cursor=next_cursor, has_more=has_more
        )

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
            and not current_user.user_role == "moderator"
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to this activity",
            )

    @staticmethod
    async def get_activity(
        activity_id: str, collection: AsyncCollection
    ) -> ActivityResponse:
        doc = await ActivityService._get_activity_doc_or_404(activity_id, collection)

        return ActivityResponse(**doc)

    @staticmethod
    async def update_activity(
        activity_id: str,
        data: ActivityUpdate,
        current_user: User,
        collection: AsyncCollection,
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

        return ActivityResponse(**result)

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
