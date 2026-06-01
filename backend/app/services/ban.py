import logging
from redis.asyncio import Redis
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.services.auth import AuthService

logger = logging.getLogger(__name__)


class BanService:
    @staticmethod
    async def ban_user(
        user_id: int,
        moderator: User,
        reason: str,
        db: AsyncSession,
        redis: Redis,
        report_id: str | None = None,
    ) -> User:
        if moderator.user_role != UserRole.moderator:
            raise HTTPException(
                status_code=403,
                detail="Permission denied",
            )

        if moderator.id == user_id:
            raise HTTPException(
                status_code=400,
                detail="You cannot ban yourself",
            )

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        if user.user_role == UserRole.moderator:
            raise HTTPException(
                status_code=400,
                detail="You cannot ban another moderator",
            )

        if user.is_banned:
            raise HTTPException(
                status_code=400,
                detail="User is already banned",
            )

        user.is_banned = True
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Revoke all active refresh sessions
        await AuthService.revoke_all_user_sessions(redis, user_id)

        # Real-time WebSocket disconnect
        try:
            from app.core.ws_manager import connection_manager

            await connection_manager.disconnect_user_globally(
                user_id=user_id,
                code=4001,
                reason="Account banned",
            )
        except Exception as e:
            logger.error(
                "Failed to globally disconnect banned user %s from WebSockets: %s",
                user_id,
                e,
            )

        logger.info(
            "User %s was banned by moderator %s. Reason: %s, Report ID: %s",
            user_id,
            moderator.id,
            reason,
            report_id,
        )

        return user

    @staticmethod
    async def unban_user(
        user_id: int,
        moderator: User,
        reason: str,
        db: AsyncSession,
    ) -> User:
        if moderator.user_role != UserRole.moderator:
            raise HTTPException(
                status_code=403,
                detail="Permission denied",
            )

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        if not user.is_banned:
            raise HTTPException(
                status_code=400,
                detail="User is not banned",
            )

        user.is_banned = False
        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(
            "User %s was unbanned by moderator %s. Reason: %s",
            user_id,
            moderator.id,
            reason,
        )

        return user

    @staticmethod
    async def get_ban_status(
        user_id: int,
        db: AsyncSession,
    ) -> bool:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )
        return user.is_banned
