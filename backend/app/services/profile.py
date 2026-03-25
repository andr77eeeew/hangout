import os
import uuid
from typing import Any

from fastapi import HTTPException, status, UploadFile
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.user import UserUpdate, PasswordUpdate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class ProfileService:

    @staticmethod
    async def update_user(user_id: int, data: UserUpdate, db: AsyncSession):
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="Nothing to Update")

        if "email" in update_data:
            check_email = await db.execute(select(User).where(User.email == update_data["email"], User.id != user_id))
            user_email = check_email.scalar_one_or_none()
            if user_email is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        if "username" in update_data:
            check_username = await db.execute(select(User).where(User.username == update_data["username"], User.id != user_id))
            user_username = check_username.scalar_one_or_none()
            if user_username is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already registered"
                )

        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(**update_data)
        )
        await db.flush()

        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one()

    @staticmethod
    async def update_password(user_id: int, data: PasswordUpdate, db: AsyncSession):

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        if not pwd_context.verify(data.old_password, user.password):
            raise HTTPException(status_code=400, detail="Old password is incorrect")

        new_password = pwd_context.hash(data.new_password)

        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(password=new_password)
        )
        await db.flush()

        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one()

    @staticmethod
    async def upload_avatar(file: UploadFile, user_id: int, db: AsyncSession, s3: Any):
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid file type. Only images are allowed.")

        content = await file.read()

        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds the limit of 5MB.")

        ext = os.path.splitext(file.filename)[1] or ".jpg"
        filename = f"{str(uuid.uuid4())}{ext}"
        old_avatar_result = await db.execute(select(User).where(User.id == user_id))
        old_avatar_user = old_avatar_result.scalar_one_or_none()
        if old_avatar_user.avatar:
            old_filename = old_avatar_user.avatar.split("/")[-1]
            try:
                s3.delete_object(Bucket=settings.BUCKET_NAME, Key=old_filename)
            except Exception:
                pass

        s3.put_object(Bucket=settings.BUCKET_NAME, Key=filename, Body=content, ContentType=file.content_type)

        avatar_url = f"{settings.BUCKET_URL}/{settings.BUCKET_NAME}/{filename}"

        await db.execute(update(User).where(User.id == user_id).values(avatar=avatar_url))
        await db.flush()

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        return user

