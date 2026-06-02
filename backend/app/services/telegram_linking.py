import json
import secrets
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.notification_preferences import NotificationPreferencesService


class TelegramLinkingService:
    @staticmethod
    async def generate_link_code(telegram_user_id: str, redis: Redis) -> str:
        for _ in range(5):
            code = f"{secrets.randbelow(1000000):06d}"
            key = f"tg_link:{code}"
            value = json.dumps({"telegram_user_id": telegram_user_id})
            # NX option ensures we only write if the key doesn't already exist
            # EX option sets TTL to 300 seconds (5 minutes)
            success = await redis.set(key, value, ex=300, nx=True)
            if success:
                return code
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate a unique linking code, please try again.",
        )

    @staticmethod
    async def link_user(
        user_id: int, code: str, db: AsyncSession, redis: Redis
    ) -> User:
        key = f"tg_link:{code}"
        # Atomic consumption of the code
        raw_val = await redis.getdel(key)
        if not raw_val:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired link code",
            )

        data = json.loads(raw_val)
        telegram_user_id = data["telegram_user_id"]

        # Check if the telegram ID is already linked to another user
        stmt = select(User).where(
            User.telegram_id == telegram_user_id, User.id != user_id
        )
        res = await db.execute(stmt)
        other_user = res.scalar_one_or_none()
        if other_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Telegram account already linked to another user",
            )

        # Retrieve the current user
        user_stmt = select(User).where(User.id == user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one()

        user.telegram_id = telegram_user_id
        await db.flush()

        # CRITICAL: Ensure the user's NotificationPreferences row exists
        await NotificationPreferencesService.get_preferences(user_id, db)

        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def unlink_user(user_id: int, db: AsyncSession) -> User:
        user_stmt = select(User).where(User.id == user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one()

        user.telegram_id = None
        await db.flush()
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def unlink_by_telegram_id(telegram_id: str, db: AsyncSession) -> None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        user.telegram_id = None
        await db.flush()
        await db.commit()
