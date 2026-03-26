from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TTL_MINUTES = 30
REFRESH_TTL_DAYS = 30


class AuthService:
    async def register(self, user_data: UserCreate, db: AsyncSession):
        result_email = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        user_email = result_email.scalar_one_or_none()
        if user_email is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        result_username = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        user_username = result_username.scalar_one_or_none()
        if user_username is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )

        new_user = User(
            email=user_data.email,
            username=user_data.username,
            password=pwd_context.hash(user_data.password),
        )

        db.add(new_user)
        try:
            await db.flush()
        except IntegrityError:
            raise HTTPException(status_code=400, detail="User already exists")
        await db.refresh(new_user)
        return UserResponse.model_validate(new_user)

    async def authenticate_user(self, email: str, password: str, db: AsyncSession):
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        if not pwd_context.verify(password, user.password):
            return None

        return user

    def create_access_token(self, user_id: int) -> str:
        utc_now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "type": "access",
            "exp": utc_now + timedelta(minutes=30),
            "iat": utc_now,
        }

        return jwt.encode(
            payload, settings.SECRET_KEY.get_secret_value(), algorithm="HS256"
        )

    def create_refresh_token(self, user_id: int) -> str:
        utc_now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "exp": utc_now + timedelta(days=30),
            "type": "refresh",
            "iat": utc_now,
        }

        return jwt.encode(
            payload, settings.SECRET_KEY.get_secret_value(), algorithm="HS256"
        )

    async def verify_refresh_token(self, token: str, db: AsyncSession) -> User:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY.get_secret_value(), algorithms=["HS256"]
            )
        except JWTError:
            raise HTTPException(status_code=400, detail="Invalid refresh token")
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Invalid refresh token")

        sub = payload.get("sub")
        try:
            user_id = int(sub)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid refresh token")

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(status_code=400, detail="Invalid refresh token")

        return user

