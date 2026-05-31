import logging
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.services.notification_preferences import NotificationPreferencesService

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    async def send_telegram_message(telegram_id: str, text: str) -> bool:
        token_secret = settings.TELEGRAM_BOT_TOKEN
        if not token_secret:
            logger.warning(
                "TELEGRAM_BOT_TOKEN is not configured. Telegram message skipped."
            )
            return False

        token = token_secret.get_secret_value()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": telegram_id,
            "text": text,
            "parse_mode": "HTML",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                response.raise_for_status()
                return True
        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending Telegram message to {telegram_id}: {e}")
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error sending Telegram message to {telegram_id}: {e}"
            )
            return False

    @staticmethod
    async def notify_membership_change(
        user_id: int, activity_title: str, change_type: str, db: AsyncSession
    ) -> None:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active or not user.telegram_id:
            return

        prefs = await NotificationPreferencesService.get_preferences(user_id, db)
        if not prefs.membership_updates:
            return

        if change_type == "approved":
            text = f"Your request to join the activity <b>{activity_title}</b> has been <b>approved</b>! 🎉"
        elif change_type == "rejected":
            text = f"Your request to join the activity <b>{activity_title}</b> has been <b>rejected</b>. 😔"
        elif change_type == "kicked":
            text = f"You have been <b>removed</b> from the activity <b>{activity_title}</b>. 🚪"
        elif change_type == "applied":
            text = f"A new user has <b>applied</b> to join your activity <b>{activity_title}</b>! 📝"
        else:
            text = f"Membership status updated for activity <b>{activity_title}</b>: <b>{change_type}</b>."

        await NotificationService.send_telegram_message(user.telegram_id, text)

    @staticmethod
    async def notify_activity_reminder(
        user_id: int, activity_title: str, starts_at_str: str, db: AsyncSession
    ) -> None:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active or not user.telegram_id:
            return

        prefs = await NotificationPreferencesService.get_preferences(user_id, db)
        if not prefs.activity_reminders:
            return

        text = f"Reminder: Activity <b>{activity_title}</b> starts at <b>{starts_at_str}</b>! 🕒"
        await NotificationService.send_telegram_message(user.telegram_id, text)

    @staticmethod
    async def notify_tag_match(
        user_id: int, activity_title: str, matched_tags: list[str], db: AsyncSession
    ) -> None:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active or not user.telegram_id:
            return

        prefs = await NotificationPreferencesService.get_preferences(user_id, db)
        if not prefs.tag_subscriptions:
            return

        formatted_tags = ", ".join(matched_tags)
        text = f"New activity <b>{activity_title}</b> matching your favorite tags: <b>{formatted_tags}</b> has been created! 🏷️"
        await NotificationService.send_telegram_message(user.telegram_id, text)
