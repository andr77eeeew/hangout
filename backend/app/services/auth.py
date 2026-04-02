from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import HTTPException, status
from jwt.exceptions import PyJWTError
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse


class AuthService:
    @staticmethod
    async def register(user_data: UserCreate, db: AsyncSession):
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            password=hash_password(user_data.password),
        )
        db.add(new_user)
        try:
            await db.flush()
            await db.commit()
            await db.refresh(new_user)
            return UserResponse.model_validate(new_user)
        except IntegrityError as e:
            error_str = str(e.orig).lower()
            if "email" in error_str:
                raise HTTPException(status_code=409, detail="Email already registered")
            if "username" in error_str:
                raise HTTPException(status_code=409, detail="Username already taken")
            raise HTTPException(status_code=409, detail="User already exists")

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
        key = AuthService._refresh_key(jti)
        user_session_key = f"user_sessions:{user_id}"

        async with redis.pipeline() as pipe:
            pipe.set(key, str(user_id), ex=ttl_seconds)
            pipe.sadd(user_session_key, jti)
            pipe.expire(user_session_key, ttl_seconds)
            await pipe.execute()

    @staticmethod
    async def revoke_all_user_sessions(redis: Redis, user_id: int) -> None:
        user_session_key = f"user_sessions:{user_id}"
        jtis = await redis.smembers(user_session_key)
        if jtis:
            keys = [AuthService._refresh_key(jti) for jti in jtis]
            await redis.delete(*keys)
        await redis.delete(user_session_key)

    @staticmethod
    async def revoke_refresh_session(redis: Redis, jti: str) -> None:
        await redis.delete(AuthService._refresh_key(jti))

    @staticmethod
    async def consume_refresh_session(redis: Redis, jti: str) -> bool:
        key = AuthService._refresh_key(jti)
        user_id_str = await redis.getdel(key)
        if user_id_str is None:
            return False
        await redis.srem(f"user_sessions:{user_id_str}", jti)
        return True
