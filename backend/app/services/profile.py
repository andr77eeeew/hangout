import os
import uuid
from typing import Any
from urllib.parse import urlparse, unquote

from fastapi import HTTPException, status, UploadFile
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.user import UserUpdate, PasswordUpdate, UserResponse
import logging

logger = logging.getLogger(__name__)

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
        try:
            await db.flush()
        except IntegrityError:
            raise HTTPException(status_code=400, detail="User already exists")
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
        if value.startswith(("http://", "https://")):
            parsed = urlparse(value)
            path = unquote(parsed.path.lstrip("/"))
            bucket_prefix = f"{settings.BUCKET_NAME}/"
            if path.startswith(bucket_prefix):
                path = path[len(bucket_prefix) :]
            return path or None
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
        data["avatar"] = ProfileService.build_image_url(
            ProfileService._normalize_image_key(user.avatar), s3_public_sign
        )
        data["banner"] = ProfileService.build_image_url(
            ProfileService._normalize_image_key(user.banner), s3_public_sign
        )
        return UserResponse(**data)

    @staticmethod
    async def _upload_user_image(
        *,
        file: UploadFile,
        user_id: int,
        db: AsyncSession,
        s3: Any,
        field_name: str,
        key_prefix: str,
        max_size_mb: int,
    ) -> User:
        content_type = file.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Only image files are allowed")

        content = await file.read()
        if len(content) > max_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=400, detail=f"File size exceeds {max_size_mb}MB"
            )

        ext = os.path.splittext(file.filename or "")[1] or ".jpg"
        object_key = f"{key_prefix}/{uuid.uuid4()}{ext}"

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        old_key = ProfileService._normalize_image_key(getattr(user, field_name))

        s3.put_object(
            Bucket=settings.BUCKET_NAME,
            Key=object_key,
            Body=content,
            ContentType=content_type,
        )

        try:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(**{field_name: object_key})
            )
            await db.flush()
        except Exception:
            try:
                s3.delete_object(Bucket=settings.BUCKET_NAME, Key=object_key)
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to cleanup uploaded object %s: %s",
                    object_key,
                    cleanup_error,
                )
            raise

        if old_key and old_key != object_key:
            try:
                s3.delete_object(Bucket=settings.BUCKET_NAME, Key=old_key)
            except Exception as delete_error:
                logger.warning(
                    "Failed to delete old object %s: %s", old_key, delete_error
                )

        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one()

    @staticmethod
    async def upload_avatar(file: UploadFile, user_id: int, db: AsyncSession, s3: Any):
        return await ProfileService._upload_user_image(
            file=file,
            user_id=user_id,
            db=db,
            s3=s3,
            field_name="avatar",
            key_prefix="avatars",
            max_size_mb=5,
        )

    @staticmethod
    async def upload_banner(file: UploadFile, user_id: int, db: AsyncSession, s3: Any):
        return await ProfileService._upload_user_image(
            file=file,
            user_id=user_id,
            db=db,
            s3=s3,
            field_name="banner",
            key_prefix="banners",
            max_size_mb=10,
        )


