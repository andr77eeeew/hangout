from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependecies import get_current_user
from app.core.storage import get_s3_client, get_s3_public_sign_client
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate, PasswordUpdate
from app.services.profile import ProfileService

router = APIRouter(prefix="/user", tags=["profile"])
profile_service = ProfileService()


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    s3_public_sign=Depends(get_s3_public_sign_client),
):
    return profile_service.to_user_response(current_user, s3_public_sign)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3_public_sign=Depends(get_s3_public_sign_client),
):
    user = await profile_service.update_user(current_user.id, data, db)
    return profile_service.to_user_response(user, s3_public_sign)


@router.patch("/password")
async def update_password(
    data: PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update = await profile_service.update_password(current_user.id, data, db)
    if update:
        return {"message": "Password updated successfully"}


@router.patch("/avatar", response_model=UserResponse)
async def update_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3=Depends(get_s3_client),
    s3_public_sign=Depends(get_s3_public_sign_client),
):
    user = await profile_service.upload_avatar(file, current_user.id, db, s3)
    return profile_service.to_user_response(user, s3_public_sign)


@router.patch("/banner", response_model=UserResponse)
async def update_banner(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3=Depends(get_s3_client),
    s3_public_sign=Depends(get_s3_public_sign_client),
):
    user = await profile_service.upload_banner(file, current_user.id, db, s3)
    return profile_service.to_user_response(user, s3_public_sign)

