from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.schemas.token import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/user", tags=["🔐 Authorization"])
auth_service = AuthService()


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    return await auth_service.register(user_data, db)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user = await auth_service.authenticate_user(form_data.email, form_data.password, db)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_service.create_access_token(user.id)
    refresh_token, jti = auth_service.create_refresh_token(user.id)
    refresh_ttl_seconds = settings.refresh_ttl_seconds

    try:
        await auth_service.store_refresh_session(
            redis=redis,
            jti=jti,
            user_id=user.id,
            ttl_seconds=refresh_ttl_seconds,
        )
    except RedisError:
        raise HTTPException(
            status_code=503, detail="Auth service temporarily unavailable"
        )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=refresh_ttl_seconds,
    )
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    try:
        user, old_jti = await auth_service.verify_refresh_token(refresh_token, db)

        if not await auth_service.consume_refresh_session(redis, old_jti):
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        new_refresh, new_jti = auth_service.create_refresh_token(user.id)
        refresh_ttl_seconds = settings.refresh_ttl_seconds
        await auth_service.store_refresh_session(
            redis=redis,
            jti=new_jti,
            user_id=user.id,
            ttl_seconds=refresh_ttl_seconds,
        )
    except RedisError:
        raise HTTPException(
            status_code=503, detail="Auth service temporarily unavailable"
        )
    access_token = auth_service.create_access_token(user.id)
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=refresh_ttl_seconds,
    )
    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):

    token = request.cookies.get("refresh_token")

    if token:
        try:
            _, jti = await auth_service.verify_refresh_token(token, db)
            await auth_service.revoke_refresh_session(redis, jti)
        except HTTPException:
            pass
        except RedisError:
            raise HTTPException(
                status_code=503, detail="Auth service temporarily unavailable"
            )

    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )
    return {"message": "Successfully logged out"}
