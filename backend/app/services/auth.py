from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from fastapi import HTTPException, status
from jwt.exceptions import PyJWTError
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class AuthService:
    @staticmethod
    async def register(user_data: UserCreate, db: AsyncSession):
        result = await db.execute(
            select(User).where(
                or_(
                    User.email == user_data.email,
                    User.username == user_data.username,
                )
            )
        )
        existing_user = result.scalar_one_or_none()

        if existing_user is not None:
            if existing_user.email == user_data.email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

        new_user = User(
            email=user_data.email,
            username=user_data.username,
            password=hash_password(user_data.password),
        )

        db.add(new_user)
        try:
            await db.flush()
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already exists",
            )
        await db.refresh(new_user)
        return UserResponse.model_validate(new_user)

    @staticmethod
    async def authenticate_user(email: str, password: str, db: AsyncSession):
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        if not verify_password(password, user.password):
            return None

        return user

    @staticmethod
    def create_access_token(user_id: int) -> str:
        utc_now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "type": "access",
            "exp": utc_now + timedelta(minutes=settings.ACCESS_TTL_MINUTES),
            "iat": utc_now,
        }

        return jwt.encode(
            payload, settings.SECRET_KEY.get_secret_value(), algorithm="HS256"
        )

    @staticmethod
    def create_refresh_token(user_id: int) -> tuple[str, str]:
        utc_now = datetime.now(timezone.utc)
        jti = uuid4().hex
        payload = {
            "sub": str(user_id),
            "exp": utc_now + timedelta(days=settings.REFRESH_TTL_DAYS),
            "jti": jti,
            "type": "refresh",
            "iat": utc_now,
        }

        return jwt.encode(
            payload, settings.SECRET_KEY.get_secret_value(), algorithm="HS256"
        ), jti

    @staticmethod
    async def verify_refresh_token(token: str, db: AsyncSession) -> tuple[User, str]:
        invalid_token = HTTPException(status_code=401, detail="Invalid refresh token")
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY.get_secret_value(), algorithms=["HS256"]
            )
        except PyJWTError:
            raise invalid_token

        if payload.get("type") != "refresh":
            raise invalid_token

        jti = payload.get("jti")
        if not isinstance(jti, str) or not jti:
            raise invalid_token

        sub = payload.get("sub")
        try:
            user_id = int(sub)
        except (ValueError, TypeError):
            raise invalid_token

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise invalid_token

        return user, jti

    @staticmethod
    def _refresh_key(jti: str) -> str:
        return f"refresh:jti:{jti}"

    @staticmethod
    async def store_refresh_session(
        redis: Redis, jti: str, user_id: int, ttl_seconds: int
    ) -> None:
        await redis.set(AuthService._refresh_key(jti), str(user_id), ex=ttl_seconds)

    @staticmethod
    async def is_refresh_session_active(redis: Redis, jti: str) -> bool:
        return bool(await redis.exists(AuthService._refresh_key(jti)))

    @staticmethod
    async def revoke_refresh_session(redis: Redis, jti: str) -> None:
        await redis.delete(AuthService._refresh_key(jti))
