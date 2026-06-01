from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.schemas.report import (
    ReportCreate,
    ReportDismiss,
    ReportListResponse,
    ReportResolve,
    ReportResponse,
    ReportStatus,
)


class ReportService:
    @staticmethod
    async def create_report(
        reporter: User,
        payload: ReportCreate,
        db: AsyncSession,
        reports_collection: AsyncCollection,
    ) -> ReportResponse:
        # Reporter cannot report themselves
        if reporter.id == payload.reported_user_id:
            raise HTTPException(
                status_code=400,
                detail="You cannot report yourself",
            )

        # reported_user_id must exist in Postgres
        stmt = select(User).where(User.id == payload.reported_user_id)
        result = await db.execute(stmt)
        reported_user = result.scalar_one_or_none()
        if reported_user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        # Reporter cannot report a moderator
        if reported_user.user_role == UserRole.moderator:
            raise HTTPException(
                status_code=400,
                detail="You cannot report a moderator/admin",
            )

        # activity_id must exist in Mongo activities collection if provided
        db_mongo = reports_collection.database
        if payload.activity_id:
            activity = await db_mongo["activities"].find_one(
                {"_id": ObjectId(payload.activity_id)}
            )
            if activity is None:
                raise HTTPException(
                    status_code=404,
                    detail="Activity not found",
                )

        # chat_message_id must exist in Mongo chat_messages collection if provided
        if payload.chat_message_id:
            message = await db_mongo["chat_messages"].find_one(
                {"_id": ObjectId(payload.chat_message_id)}
            )
            if message is None:
                raise HTTPException(
                    status_code=404,
                    detail="Chat message not found",
                )

        # Prevent duplicate active reports
        dup_query = {
            "reporter_id": reporter.id,
            "reported_user_id": payload.reported_user_id,
            "status": {"$in": ["open", "in_review"]},
            "activity_id": ObjectId(payload.activity_id)
            if payload.activity_id
            else None,
            "chat_message_id": ObjectId(payload.chat_message_id)
            if payload.chat_message_id
            else None,
        }
        existing = await reports_collection.find_one(dup_query)
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="You have already reported this user in this context",
            )

        now = datetime.now(timezone.utc)
        report_doc = {
            "reporter_id": reporter.id,
            "reported_user_id": payload.reported_user_id,
            "activity_id": ObjectId(payload.activity_id)
            if payload.activity_id
            else None,
            "chat_message_id": ObjectId(payload.chat_message_id)
            if payload.chat_message_id
            else None,
            "reason": payload.reason,
            "status": ReportStatus.open.value,
            "moderator_id": None,
            "moderator_notes": None,
            "resolution": None,
            "created_at": now,
            "updated_at": now,
            "taken_at": None,
            "resolved_at": None,
        }

        res = await reports_collection.insert_one(report_doc)
        report_doc["_id"] = res.inserted_id
        return ReportResponse(**report_doc)

    @staticmethod
    async def list_reports(
        moderator: User,
        status: ReportStatus | None,
        cursor: str | None,
        limit: int,
        reports_collection: AsyncCollection,
    ) -> ReportListResponse:
        # Only moderators can list reports
        if moderator.user_role != UserRole.moderator:
            raise HTTPException(
                status_code=403,
                detail="Permission denied",
            )

        query = {}
        if status is not None:
            query["status"] = status.value

        count_query = query.copy()

        if cursor is not None:
            if not ObjectId.is_valid(cursor):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid cursor",
                )
            query["_id"] = {"$lt": ObjectId(cursor)}

        limit = min(max(1, limit), 100)

        total = await reports_collection.count_documents(count_query)

        cursor_obj = reports_collection.find(query).sort("_id", -1).limit(limit + 1)
        reports = await cursor_obj.to_list(length=limit + 1)

        has_more = len(reports) > limit
        if has_more:
            items_docs = reports[:limit]
            next_cursor = str(items_docs[-1]["_id"])
        else:
            items_docs = reports
            next_cursor = None

        return ReportListResponse(
            items=[ReportResponse(**doc) for doc in items_docs],
            total=total,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    @staticmethod
    async def take_report(
        report_id: str,
        moderator: User,
        reports_collection: AsyncCollection,
    ) -> ReportResponse:
        # Only moderators can take reports
        if moderator.user_role != UserRole.moderator:
            raise HTTPException(
                status_code=403,
                detail="Permission denied",
            )

        if not ObjectId.is_valid(report_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid report id",
            )

        report = await reports_collection.find_one({"_id": ObjectId(report_id)})
        if report is None:
            raise HTTPException(
                status_code=404,
                detail="Report not found",
            )

        # Only open reports can be taken
        if report["status"] != ReportStatus.open.value:
            raise HTTPException(
                status_code=400,
                detail="Only open reports can be taken",
            )

        now = datetime.now(timezone.utc)
        updated = await reports_collection.find_one_and_update(
            {"_id": ObjectId(report_id)},
            {
                "$set": {
                    "status": ReportStatus.in_review.value,
                    "moderator_id": moderator.id,
                    "taken_at": now,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        assert updated is not None
        return ReportResponse(**updated)

    @staticmethod
    async def resolve_report(
        report_id: str,
        moderator: User,
        payload: ReportResolve,
        db: AsyncSession,
        redis: Redis,
        reports_collection: AsyncCollection,
    ) -> ReportResponse:
        # Only moderators can resolve reports
        if moderator.user_role != UserRole.moderator:
            raise HTTPException(
                status_code=403,
                detail="Permission denied",
            )

        if not ObjectId.is_valid(report_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid report id",
            )

        report = await reports_collection.find_one({"_id": ObjectId(report_id)})
        if report is None:
            raise HTTPException(
                status_code=404,
                detail="Report not found",
            )

        # Only in_review reports can be resolved
        if report["status"] != ReportStatus.in_review.value:
            raise HTTPException(
                status_code=400,
                detail="Only reports in review can be resolved/dismissed",
            )

        # Only the assigned moderator can resolve
        if report.get("moderator_id") != moderator.id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned moderator can resolve/dismiss this report",
            )

        # Handle ban_user if True
        if payload.ban_user:
            from app.services.ban import BanService

            await BanService.ban_user(
                user_id=report["reported_user_id"],
                moderator=moderator,
                reason=payload.ban_reason or payload.resolution,
                db=db,
                redis=redis,
                report_id=report_id,
            )

        now = datetime.now(timezone.utc)
        updated = await reports_collection.find_one_and_update(
            {"_id": ObjectId(report_id)},
            {
                "$set": {
                    "status": ReportStatus.resolved.value,
                    "resolution": payload.resolution,
                    "moderator_notes": payload.moderator_notes,
                    "resolved_at": now,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        assert updated is not None

        try:
            from app.services.notification import NotificationService

            await NotificationService.notify_report_update(
                user_id=report["reporter_id"],
                report_id=report_id,
                status="resolved",
                resolution=payload.resolution,
                db=db,
            )
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(
                f"Failed to send report update notification for report {report_id}: {e}"
            )

        return ReportResponse(**updated)

    @staticmethod
    async def dismiss_report(
        report_id: str,
        moderator: User,
        payload: ReportDismiss,
        db: AsyncSession,
        reports_collection: AsyncCollection,
    ) -> ReportResponse:
        # Only moderators can dismiss reports
        if moderator.user_role != UserRole.moderator:
            raise HTTPException(
                status_code=403,
                detail="Permission denied",
            )

        if not ObjectId.is_valid(report_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid report id",
            )

        report = await reports_collection.find_one({"_id": ObjectId(report_id)})
        if report is None:
            raise HTTPException(
                status_code=404,
                detail="Report not found",
            )

        # Only in_review reports can be dismissed
        if report["status"] != ReportStatus.in_review.value:
            raise HTTPException(
                status_code=400,
                detail="Only reports in review can be resolved/dismissed",
            )

        # Only the assigned moderator can dismiss
        if report.get("moderator_id") != moderator.id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned moderator can resolve/dismiss this report",
            )

        now = datetime.now(timezone.utc)
        updated = await reports_collection.find_one_and_update(
            {"_id": ObjectId(report_id)},
            {
                "$set": {
                    "status": ReportStatus.dismissed.value,
                    "resolution": payload.resolution,
                    "moderator_notes": payload.moderator_notes,
                    "resolved_at": now,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        assert updated is not None

        try:
            from app.services.notification import NotificationService

            await NotificationService.notify_report_update(
                user_id=report["reporter_id"],
                report_id=report_id,
                status="dismissed",
                resolution=payload.resolution,
                db=db,
            )
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(
                f"Failed to send report update notification for report {report_id}: {e}"
            )

        return ReportResponse(**updated)

    @staticmethod
    async def get_user_reports(
        user_id: int,
        moderator: User,
        cursor: str | None,
        limit: int,
        db: AsyncSession,
        reports_collection: AsyncCollection,
    ) -> ReportListResponse:
        # Only moderators can view user report history
        if moderator.user_role != UserRole.moderator:
            raise HTTPException(
                status_code=403,
                detail="Permission denied",
            )

        # user_id must exist in Postgres
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        query = {"reported_user_id": user_id}
        count_query = query.copy()

        if cursor is not None:
            if not ObjectId.is_valid(cursor):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid cursor",
                )
            query["_id"] = {"$lt": ObjectId(cursor)}

        limit = min(max(1, limit), 100)

        total = await reports_collection.count_documents(count_query)

        cursor_obj = reports_collection.find(query).sort("_id", -1).limit(limit + 1)
        reports = await cursor_obj.to_list(length=limit + 1)

        has_more = len(reports) > limit
        if has_more:
            items_docs = reports[:limit]
            next_cursor = str(items_docs[-1]["_id"])
        else:
            items_docs = reports
            next_cursor = None

        return ReportListResponse(
            items=[ReportResponse(**doc) for doc in items_docs],
            total=total,
            next_cursor=next_cursor,
            has_more=has_more,
        )
