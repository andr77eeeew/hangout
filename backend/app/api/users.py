from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.redis_client import get_redis
from app.models.user import User
from app.schemas.ban import BanUserRequest, UnbanUserRequest
from app.schemas.user import UserResponse
from app.services.ban import BanService

router = APIRouter(prefix="/users", tags=["👤 Users & Moderation"])


@router.post("/{user_id}/ban", response_model=UserResponse)
async def ban_user(
    user_id: int,
    payload: BanUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    return await BanService.ban_user(
        user_id=user_id,
        moderator=current_user,
        reason=payload.reason,
        db=db,
        redis=redis,
    )


@router.post("/{user_id}/unban", response_model=UserResponse)
async def unban_user(
    user_id: int,
    payload: UnbanUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await BanService.unban_user(
        user_id=user_id,
        moderator=current_user,
        reason=payload.reason,
        db=db,
    )
