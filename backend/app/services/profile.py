import os
import uuid
from typing import Any

from fastapi import HTTPException, status, UploadFile
from passlib.context import CryptContext
from sqlalchemy import select, update, exc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.user import UserUpdate, PasswordUpdate, UserResponse

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class ProfileService:
    @staticmethod
    async def update_user(user_id: int, data: UserUpdate, db: AsyncSession):
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="Nothing to Update")

        if "email" in update_data:
            check_email = await db.execute(
                select(User).where(
                    User.email == update_data["email"], User.id != user_id
                )
            )
            user_email = check_email.scalar_one_or_none()
            if user_email is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )
        if "username" in update_data:
            check_username = await db.execute(
                select(User).where(
                    User.username == update_data["username"], User.id != user_id
                )
            )
            user_username = check_username.scalar_one_or_none()
            if user_username is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already registered",
                )

        await db.execute(update(User).where(User.id == user_id).values(**update_data))
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
            update(User).where(User.id == user_id).values(password=new_password)
        )
        await db.flush()

        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one()

    @staticmethod
    def _normalize_image_key(value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("http://") or value.startswith("https://"):
            return value.rsplit("/", 1)[1]
        return value

    @staticmethod
    def build_image_url(image_key: str | None, s3_public_sign) -> str | None:
        if not image_key:
            return None
        return s3_public_sign.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.BUCKET_NAME, "Key": image_key},
            ExpiresIn=settings.PRESIGNED_URL_EXPIRES_SECONDS,
        )

    @staticmethod
    def to_user_response(user: User, s3_public_sign):
        data = UserResponse.model_validate(user).model_dump()
        avatar_key = ProfileService._normalize_image_key(user.avatar)
        banner_key = ProfileService._normalize_image_key(user.banner)
        data["avatar"] = ProfileService.build_image_url(avatar_key, s3_public_sign)
        data["banner"] = ProfileService.build_image_url(banner_key, s3_public_sign)
        return UserResponse(**data)

    @staticmethod
    async def upload_avatar(file: UploadFile, user_id: int, db: AsyncSession, s3: Any):
        content_type = file.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=400, detail="Invalid file type. Only images are allowed."
            )

        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400, detail="File size exceeds the limit of 5MB."
            )

        ext = os.path.splitext(file.filename or "")[1] or ".jpg"
        object_key = f"avatars/{str(uuid.uuid4())}{ext}"

        old_avatar_result = await db.execute(select(User).where(User.id == user_id))
        old_avatar_user = old_avatar_result.scalar_one_or_none()
        old_key = ProfileService._normalize_image_key(old_avatar_user.avatar)
        if old_key:
            try:
                s3.delete_object(Bucket=settings.BUCKET_NAME, Key=old_key)
            except Exception:
                pass

        s3.put_object(
            Bucket=settings.BUCKET_NAME,
            Key=object_key,
            Body=content,
            ContentType=content_type,
        )

        await db.execute(
            update(User).where(User.id == user_id).values(avatar=object_key)
        )
        await db.flush()

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        return user

    @staticmethod
    async def upload_banner(file: UploadFile, user_id: int, db: AsyncSession, s3: Any):
        content_type = file.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=400, detail="Invalid file type. Only images are allowed."
            )

        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400, detail="File size exceeds the limit of 10MB."
            )

        ext = os.path.splitext(file.filename or "")[1] or ".jpg"
        object_key = f"banners/{str(uuid.uuid4())}{ext}"

        old_banner_result = await db.execute(select(User).where(User.id == user_id))
        old_banner_user = old_banner_result.scalar_one_or_none()
        old_key = ProfileService._normalize_image_key(old_banner_user.banner)
        if old_key:
            try:
                s3.delete_object(Bucket=settings.BUCKET_NAME, Key=old_key)
            except Exception:
                pass

        s3.put_object(
            Bucket=settings.BUCKET_NAME,
            Key=object_key,
            Body=content,
            ContentType=content_type,
        )

        await db.execute(
            update(User).where(User.id == user_id).values(banner=object_key)
        )
        await db.flush()

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        return user

