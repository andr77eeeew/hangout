from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_preferences import NotificationPreferences
from app.schemas.notifications import NotificationPreferencesUpdate


class NotificationPreferencesService:
    @staticmethod
    async def get_preferences(
        user_id: int, db: AsyncSession
    ) -> NotificationPreferences:
        result = await db.execute(
            select(NotificationPreferences).where(
                NotificationPreferences.user_id == user_id
            )
        )
        prefs = result.scalar_one_or_none()
        if prefs is None:
            prefs = NotificationPreferences(
                user_id=user_id,
                membership_updates=True,
                activity_reminders=True,
                tag_subscriptions=True,
            )
            db.add(prefs)
            await db.flush()
            await db.commit()
            await db.refresh(prefs)
        return prefs

    @staticmethod
    async def update_preferences(
        user_id: int, data: NotificationPreferencesUpdate, db: AsyncSession
    ) -> NotificationPreferences:
        prefs = await NotificationPreferencesService.get_preferences(user_id, db)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                if key == "membership_updates":
                    prefs.membership_updates = value
                elif key == "activity_reminders":
                    prefs.activity_reminders = value
                elif key == "tag_subscriptions":
                    prefs.tag_subscriptions = value
        await db.flush()
        await db.commit()
        await db.refresh(prefs)
        return prefs
