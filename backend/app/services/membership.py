from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.asynchronous.collection import AsyncCollection, ReturnDocument
from pymongo.errors import DuplicateKeyError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.image_utils import build_image_url
from app.models.user import User
from app.schemas.membership import (
    MemberPreview,
    MembershipListResponse,
    MembershipResponse,
    MembershipStatus,
)


class MembershipService:
    @staticmethod
    async def _get_active_activity_or_400(
        activity_id: str,
        activities_col: AsyncCollection,
    ) -> dict:
        if not ObjectId.is_valid(activity_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid activity id"
            )
        doc = await activities_col.find_one({"_id": ObjectId(activity_id)})
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found"
            )
        if doc["status"] != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity is not active",
            )
        return doc

    @staticmethod
    async def join_activity(
        user_id: int,
        activity_id: str,
        activities_col: AsyncCollection,
        membership_col: AsyncCollection,
    ) -> MembershipResponse:
        activity = await MembershipService._get_active_activity_or_400(
            activity_id, activities_col
        )

        if activity["creator_id"] == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot join own activity",
            )

        if activity["current_members"] >= activity["max_members"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity is full",
            )

        if activity["type"] == "open":
            membership_status = MembershipStatus.approved
        else:
            membership_status = MembershipStatus.pending

        now = datetime.now(timezone.utc)
        membership_doc = {
            "activity_id": ObjectId(activity_id),
            "user_id": user_id,
            "status": membership_status.value,
            "joined_at": now,
        }

        try:
            result = await membership_col.insert_one(membership_doc)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Already applied to this activity",
            )

        if membership_status == MembershipStatus.approved:
            updated = await activities_col.find_one_and_update(
                {
                    "_id": ObjectId(activity_id),
                    "current_members": {"$lt": activity["max_members"]},
                },
                {"$inc": {"current_members": 1}},
            )
            if updated is None:
                await membership_col.delete_one({"_id": result.inserted_id})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Activity is full",
                )
        created = await membership_col.find_one({"_id": result.inserted_id})
        assert created is not None
        if activity["type"] == "closed":
            from app.tasks.notifications import notify_membership_change_task

            notify_membership_change_task.delay(
                user_id=activity["creator_id"],
                activity_title=activity.get("title") or "Unnamed Activity",
                change_type="applied",
            )
        return MembershipResponse(**created, user_preview=None)

    @staticmethod
    async def _get_membership_or_404(
        membership_id: str,
        membership_col: AsyncCollection,
    ) -> dict:
        if not ObjectId.is_valid(membership_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid membership id",
            )
        doc = await membership_col.find_one({"_id": ObjectId(membership_id)})
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Membership not found",
            )
        return doc

    @staticmethod
    async def _check_creator_or_moderator(
        activity_id: ObjectId,
        user_id: int,
        is_moderator: bool,
        activities_col: AsyncCollection,
    ) -> dict:
        """Fetch activity and verify the user is its creator or a moderator."""
        activity = await activities_col.find_one({"_id": activity_id})
        if activity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity not found",
            )
        if activity["creator_id"] != user_id and not is_moderator:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the activity creator can manage members",
            )
        return activity

    @staticmethod
    async def approve_member(
        user_id: int,
        is_moderator: bool,
        membership_id: str,
        activities_col: AsyncCollection,
        membership_col: AsyncCollection,
    ) -> MembershipResponse:
        membership = await MembershipService._get_membership_or_404(
            membership_id, membership_col
        )

        activity = await MembershipService._check_creator_or_moderator(
            membership["activity_id"], user_id, is_moderator, activities_col
        )

        if membership["status"] != MembershipStatus.pending.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending memberships can be approved",
            )

        # Atomic increment with race condition guard
        updated_activity = await activities_col.find_one_and_update(
            {
                "_id": membership["activity_id"],
                "current_members": {"$lt": activity["max_members"]},
            },
            {"$inc": {"current_members": 1}},
        )
        if updated_activity is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity is full",
            )

        updated = await membership_col.find_one_and_update(
            {"_id": membership["_id"]},
            {"$set": {"status": MembershipStatus.approved.value}},
            return_document=ReturnDocument.AFTER,
        )
        assert updated is not None
        from app.tasks.notifications import notify_membership_change_task

        notify_membership_change_task.delay(
            user_id=membership["user_id"],
            activity_title=activity.get("title") or "Unnamed Activity",
            change_type="approved",
        )
        return MembershipResponse(**updated, user_preview=None)

    @staticmethod
    async def reject_member(
        user_id: int,
        is_moderator: bool,
        membership_id: str,
        activities_col: AsyncCollection,
        membership_col: AsyncCollection,
    ) -> MembershipResponse:
        membership = await MembershipService._get_membership_or_404(
            membership_id, membership_col
        )

        activity = await MembershipService._check_creator_or_moderator(
            membership["activity_id"], user_id, is_moderator, activities_col
        )

        if membership["status"] != MembershipStatus.pending.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending memberships can be rejected",
            )

        updated = await membership_col.find_one_and_update(
            {"_id": membership["_id"]},
            {"$set": {"status": MembershipStatus.rejected.value}},
            return_document=ReturnDocument.AFTER,
        )
        assert updated is not None
        from app.tasks.notifications import notify_membership_change_task

        notify_membership_change_task.delay(
            user_id=membership["user_id"],
            activity_title=activity.get("title") or "Unnamed Activity",
            change_type="rejected",
        )
        return MembershipResponse(**updated, user_preview=None)

    @staticmethod
    async def kick_member(
        user_id: int,
        is_moderator: bool,
        membership_id: str,
        activities_col: AsyncCollection,
        membership_col: AsyncCollection,
    ) -> MembershipResponse:
        membership = await MembershipService._get_membership_or_404(
            membership_id, membership_col
        )

        activity = await MembershipService._check_creator_or_moderator(
            membership["activity_id"], user_id, is_moderator, activities_col
        )

        if membership["status"] != MembershipStatus.approved.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only approved members can be kicked",
            )

        # Prevent kicking the creator (they have a membership record too)
        if membership["user_id"] == user_id and not is_moderator:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot kick yourself",
            )

        updated = await membership_col.find_one_and_update(
            {"_id": membership["_id"]},
            {"$set": {"status": MembershipStatus.kicked.value}},
            return_document=ReturnDocument.AFTER,
        )

        # Atomic decrement with guard: current_members never below 1 (creator)
        await activities_col.find_one_and_update(
            {
                "_id": membership["activity_id"],
                "current_members": {"$gt": 1},
            },
            {"$inc": {"current_members": -1}},
        )
        assert updated is not None
        from app.tasks.notifications import notify_membership_change_task

        notify_membership_change_task.delay(
            user_id=membership["user_id"],
            activity_title=activity.get("title") or "Unnamed Activity",
            change_type="kicked",
        )
        return MembershipResponse(**updated, user_preview=None)

    @staticmethod
    async def leave_activity(
        user_id: int,
        activity_id: str,
        activities_col: AsyncCollection,
        membership_col: AsyncCollection,
    ) -> None:
        if not ObjectId.is_valid(activity_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid activity id",
            )

        # Creator cannot leave their own activity
        activity = await activities_col.find_one({"_id": ObjectId(activity_id)})
        if activity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity not found",
            )
        if activity["creator_id"] == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Creator cannot leave own activity",
            )

        membership = await membership_col.find_one(
            {
                "activity_id": ObjectId(activity_id),
                "user_id": user_id,
                "status": MembershipStatus.approved.value,
            }
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active membership not found",
            )

        await membership_col.update_one(
            {"_id": membership["_id"]},
            {"$set": {"status": MembershipStatus.left.value}},
        )

        # Atomic decrement with guard
        await activities_col.find_one_and_update(
            {
                "_id": ObjectId(activity_id),
                "current_members": {"$gt": 1},
            },
            {"$inc": {"current_members": -1}},
        )

    @staticmethod
    async def list_members(
        activity_id: str,
        current_user_id: int,
        is_moderator: bool,
        activities_col: AsyncCollection,
        membership_col: AsyncCollection,
        db: AsyncSession,
        s3_public_sign,
    ) -> MembershipListResponse:
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

        is_creator_or_mod = (activity["creator_id"] == current_user_id) or is_moderator

        if is_creator_or_mod:
            allowed_statuses = [
                MembershipStatus.approved.value,
                MembershipStatus.pending.value,
            ]
        else:
            allowed_statuses = [MembershipStatus.approved.value]

        cursor = membership_col.find(
            {
                "activity_id": ObjectId(activity_id),
                "status": {"$in": allowed_statuses},
            }
        )
        memberships = await cursor.to_list(length=None)

        user_ids = {m["user_id"] for m in memberships}
        users_map = {}
        if user_ids:
            result = await db.execute(
                select(User).where(
                    User.id.in_(user_ids),
                    User.is_active.is_(True),
                )
            )
            users = result.scalars().all()
            users_map = {user.id: user for user in users}

        items = []
        for m in memberships:
            user = users_map.get(m["user_id"])
            preview = None
            if user:
                preview = MemberPreview(
                    id=user.id,
                    username=user.username,
                    avatar_url=build_image_url(user.avatar, s3_public_sign)
                    if user.avatar
                    else None,
                )

            items.append(
                MembershipResponse(
                    **m,
                    user_preview=preview,
                )
            )

        return MembershipListResponse(items=items, total=len(items))

    @staticmethod
    async def get_my_membership(
        user_id: int,
        activity_id: str,
        membership_col: AsyncCollection,
    ) -> MembershipResponse | None:
        if not ObjectId.is_valid(activity_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid activity id",
            )

        doc = await membership_col.find_one(
            {
                "activity_id": ObjectId(activity_id),
                "user_id": user_id,
            }
        )
        if doc is None:
            return None

        return MembershipResponse(**doc, user_preview=None)
