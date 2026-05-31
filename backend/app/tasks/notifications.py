import asyncio
from datetime import datetime, timedelta, timezone
import logging
from bson import ObjectId
from celery import Task
from slugify import slugify
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.celery_config import celery_app
from app.core.mongo import (
    get_activities_collection,
    get_membership_collection,
    init_mongo,
    close_mongo,
)
from app.core.redis_client import get_redis
from app.core.database import AsyncSessionLocal
from app.models.tags import Tag, UserTag
from app.models.user import User
from app.models.notification_preferences import NotificationPreferences
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


async def async_check_activity_reminders() -> None:
    now = datetime.now(timezone.utc)
    start_window = now + timedelta(hours=1, minutes=45)
    end_window = now + timedelta(hours=2, minutes=15)

    activities_col = await get_activities_collection()
    membership_col = await get_membership_collection()

    cursor = activities_col.find(
        {"status": "active", "date": {"$gte": start_window, "$lte": end_window}}
    )
    activities = await cursor.to_list(length=1000)

    if not activities:
        return

    redis = await get_redis()

    async with AsyncSessionLocal() as db:
        for activity in activities:
            activity_id = str(activity["_id"])

            dedup_key = f"reminded:{activity_id}"
            is_new = await redis.set(dedup_key, "1", ex=10800, nx=True)
            if not is_new:
                continue

            cursor_members = membership_col.find(
                {"activity_id": ObjectId(activity_id), "status": "approved"}
            )
            members = await cursor_members.to_list(length=1000)

            activity_title = str(activity["title"])
            starts_at_dt = activity["date"]
            if starts_at_dt.tzinfo is None:
                starts_at_dt = starts_at_dt.replace(tzinfo=timezone.utc)
            starts_at_str = starts_at_dt.strftime("%Y-%m-%d %H:%M UTC")

            for member in members:
                user_id = int(member["user_id"])
                await NotificationService.notify_activity_reminder(
                    user_id=user_id,
                    activity_title=activity_title,
                    starts_at_str=starts_at_str,
                    db=db,
                )


@celery_app.task(bind=True)
def check_activity_reminders(self: Task) -> None:
    async def runner() -> None:
        await init_mongo()
        try:
            await async_check_activity_reminders()
        finally:
            await close_mongo()

    asyncio.run(runner())


@celery_app.task(bind=True)
def notify_tag_matching_users(self: Task, activity_id: str) -> None:
    async def runner() -> None:
        await init_mongo()
        try:
            await async_notify_tag_matching_users(activity_id)
        finally:
            await close_mongo()

    asyncio.run(runner())


async def async_notify_tag_matching_users(activity_id: str) -> None:
    if not ObjectId.is_valid(activity_id):
        logger.warning(f"Invalid activity_id: {activity_id}")
        return

    activities_col = await get_activities_collection()
    activity = await activities_col.find_one({"_id": ObjectId(activity_id)})
    if not activity:
        logger.warning(f"Activity not found: {activity_id}")
        return

    activity_tags: list[str] = activity.get("tags") or []
    if not activity_tags:
        logger.info(f"Activity {activity_id} has no tags. Skipping notifications.")
        return

    creator_id = activity.get("creator_id")
    if creator_id is None:
        logger.warning(
            f"Activity {activity_id} has no creator_id. Skipping notifications."
        )
        return
    creator_id = int(creator_id)

    tag_slugs = [slugify(t) for t in activity_tags]

    async with AsyncSessionLocal() as db:
        tag_ids_stmt = select(Tag.id).where(Tag.slug.in_(tag_slugs))
        tag_ids_result = await db.execute(tag_ids_stmt)
        tag_ids = list(tag_ids_result.scalars().all())

        if not tag_ids:
            logger.info(
                f"No tag IDs found for slugs: {tag_slugs}. Skipping notifications."
            )
            return

        stmt = (
            select(User)
            .join(UserTag, User.id == UserTag.user_id)
            .join(NotificationPreferences, User.id == NotificationPreferences.user_id)
            .where(
                UserTag.tag_id.in_(tag_ids),
                User.is_active.is_(True),
                User.telegram_id.is_not(None),
                User.telegram_id != "",
                User.id != creator_id,
                NotificationPreferences.tag_subscriptions.is_(True),
            )
            .options(selectinload(User.favorite_tags))
            .distinct()
        )
        users_result = await db.execute(stmt)
        users = users_result.scalars().all()

        for user in users:
            matched_tag_names = [
                tag.name for tag in user.favorite_tags if tag.slug in tag_slugs
            ]
            if not matched_tag_names:
                continue

            activity_title = activity.get("title") or "Unnamed Activity"
            await NotificationService.notify_tag_match(
                user_id=user.id,
                activity_title=activity_title,
                matched_tags=matched_tag_names,
                db=db,
            )


@celery_app.task(bind=True)
def notify_membership_change_task(
    self: Task, user_id: int, activity_title: str, change_type: str
) -> None:
    async def runner() -> None:
        async with AsyncSessionLocal() as db:
            await NotificationService.notify_membership_change(
                user_id=user_id,
                activity_title=activity_title,
                change_type=change_type,
                db=db,
            )

    asyncio.run(runner())
