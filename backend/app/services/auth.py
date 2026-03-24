from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:

    async def register(self, user_data: UserCreate, db: AsyncSession):
        result_email = await db.execute(select(User).where(User.email == user_data.email))
        user_email = result_email.scalar_one_or_none()
        if user_email is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        result_username = await db.execute(select(User).where(User.username == user_data.username))
        user_username = result_username.scalar_one_or_none()
        if user_username is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )

        new_user = User(
            email=user_data.email,
            username=user_data.username,
            password=pwd_context.hash(user_data.password)
        )

        db.add(new_user)
        await db.flush()
        await db.refresh(new_user)
        return UserResponse.model_validate(new_user)


