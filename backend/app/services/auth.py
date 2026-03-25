from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
        await db.flush()
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
        payload = {"sub": str(user_id), "exp": utc_now + timedelta(minutes=30)}

        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def create_refresh_token(self, user_id: int) -> str:
        utc_now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "exp": utc_now + timedelta(days=30),
            "type": "refresh",
        }

        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    async def verify_refresh_token(self, token: str, db: AsyncSession) -> User:
        try:
            refresh = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except JWTError:
            raise HTTPException(status_code=400, detail="Invalid refresh token")
        type = refresh["type"]
        if type != "refresh":
            raise HTTPException(status_code=400, detail="Invalid refresh token")
        user = await db.execute(select(User).where(User.id == int(refresh["sub"])))
        user = user.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=400, detail="Invalid refresh token")
        return user

