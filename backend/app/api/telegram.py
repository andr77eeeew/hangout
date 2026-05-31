from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.internal_auth import verify_internal_api_key
from app.core.redis_client import get_redis
from app.models.user import User
from app.schemas.notifications import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)
from app.schemas.telegram import (
    TelegramLinkCodeRequest,
    TelegramLinkCodeResponse,
    TelegramUserResponse,
)
from app.services.notification_preferences import NotificationPreferencesService
from app.services.telegram_linking import TelegramLinkingService

router = APIRouter(
    prefix="/internal/telegram",
    tags=["🤖 Telegram Bot Internal API"],
    dependencies=[Depends(verify_internal_api_key)],
)


@router.post("/link-code", response_model=TelegramLinkCodeResponse)
async def generate_link_code(
    data: TelegramLinkCodeRequest,
    redis: Redis = Depends(get_redis),
):
    code = await TelegramLinkingService.generate_link_code(data.telegram_user_id, redis)
    return TelegramLinkCodeResponse(code=code)


@router.get("/users/{telegram_id}", response_model=TelegramUserResponse)
async def get_user_by_telegram_id(
    telegram_id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.telegram_id == telegram_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hangout user not found for the given telegram_id",
        )
    return user


@router.get(
    "/users/{telegram_id}/notification-preferences",
    response_model=NotificationPreferencesResponse,
)
async def get_telegram_user_preferences(
    telegram_id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.telegram_id == telegram_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hangout user not found for the given telegram_id",
        )
    # Lazy-on-read via service
    return await NotificationPreferencesService.get_preferences(user.id, db)


@router.patch(
    "/users/{telegram_id}/notification-preferences",
    response_model=NotificationPreferencesResponse,
)
async def update_telegram_user_preferences(
    telegram_id: str,
    data: NotificationPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.telegram_id == telegram_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hangout user not found for the given telegram_id",
        )
    return await NotificationPreferencesService.update_preferences(user.id, data, db)


@router.delete("/users/{telegram_id}/link")
async def unlink_telegram_user(
    telegram_id: str,
    db: AsyncSession = Depends(get_db),
):
    await TelegramLinkingService.unlink_by_telegram_id(telegram_id, db)
    return {"message": "Unlinked successfully"}
