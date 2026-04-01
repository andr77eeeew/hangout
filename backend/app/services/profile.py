import logging
import os
import uuid
from typing import Any

from app.core.config import settings
from app.core.image_utils import build_image_url, normalize_image_key
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import PasswordUpdate, UserResponse, UserUpdate
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


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
            await db.commit()
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

        if not verify_password(data.old_password, user.password):
            raise HTTPException(status_code=400, detail="Old password is incorrect")

        new_hashed = hash_password(data.new_password)

        await db.execute(
            update(User).where(User.id == user_id).values(password=new_hashed)
        )
        await db.flush()
        await db.commit()

    @staticmethod
    def to_user_response(user: User, s3_public_sign):
        data = UserResponse.model_validate(user).model_dump()
        data["avatar"] = build_image_url(
            normalize_image_key(user.avatar), s3_public_sign
        )
        data["banner"] = build_image_url(
            normalize_image_key(user.banner), s3_public_sign
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

        ext = os.path.splitext(file.filename or "")[1] or ".jpg"
        object_key = f"{key_prefix}/{uuid.uuid4()}{ext}"

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        old_key = normalize_image_key(getattr(user, field_name))

        await run_in_threadpool(
            s3.put_object,
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
            await db.commit()
        except Exception:
            try:
                await run_in_threadpool(
                    s3.delete_object, Bucket=settings.BUCKET_NAME, Key=object_key
                )
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to cleanup uploaded object %s: %s",
                    object_key,
                    cleanup_error,
                )
            raise

        if old_key and old_key != object_key:
            try:
                await run_in_threadpool(
                    s3.delete_object, Bucket=settings.BUCKET_NAME, Key=old_key
                )
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
