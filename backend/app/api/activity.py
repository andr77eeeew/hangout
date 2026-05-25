from fastapi import APIRouter, Depends, Query, status
from pymongo.asynchronous.collection import AsyncCollection
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.mongo import get_activities_collection
from app.core.storage import get_s3_public_sign_client
from app.models.user import User
from app.schemas.activity import (
    ActivityCreate,
    ActivityResponse,
    ActivityResponseFeed,
    ActivityUpdate,
)
from app.schemas.common import ErrorResponse
from app.services.activity import ActivityService

router = APIRouter(prefix="/activities", tags=["🎮 Activity"])
activity_service = ActivityService()


@router.post(
    "/",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="🌟 Create a new activity",
    description="""
    Creates a new collaborative meeting (`Activity`).

    The method validates the category:
    * The attached data (`extra_data`) must strictly match the selected `category`.
    * If it is board games (`board_games`), then `extra_data` must contain `player_count`.
    * If the format is `offline`, it will return a 400 error without `location`.
    """,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Logical validation error (e.g., time constraint not met or location field is empty for offline mode)",
        },
        401: {
            "model": ErrorResponse,
            "description": "Token is invalid (Unauthorized)",
        },
    },
)
async def create_activity(
    activity_data: ActivityCreate,
    current_user: User = Depends(get_current_user),
    collection: AsyncCollection = Depends(get_activities_collection),
    db: AsyncSession = Depends(get_db),
    s3_public_sign=Depends(get_s3_public_sign_client),
):
    return await activity_service.create_activity(
        activity_data=activity_data,
        creator_id=current_user.id,
        collection=collection,
        db=db,
        s3_public_sign=s3_public_sign,
    )


@router.get(
    "/feed",
    response_model=ActivityResponseFeed,
    status_code=status.HTTP_200_OK,
    summary="📜 View the main feed",
    description="""
  Returns a list of active events. 
  Uses **Cursor Pagination** (`cursor`) for fast and seamless loading (infinite scroll).
  Instead of `page=2`, the frontend retrieves the `next_cursor` field from the response and includes it in the next request!
  """,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "A non-existent or invalid cursor (ObjectId) was passed",
        }
    },
)
async def get_activities(
    db: AsyncSession = Depends(get_db),
    collection: AsyncCollection = Depends(get_activities_collection),
    s3_public_sign=Depends(get_s3_public_sign_client),
    limit: int = (Query(10, ge=1, le=50)),
    cursor: str | None = None,
):
    return await activity_service.list_feed(
        collection=collection,
        db=db,
        s3_public_sign=s3_public_sign,
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/{activity_id}", response_model=ActivityResponse, status_code=status.HTTP_200_OK
)
async def get_current_activity(
    activity_id: str,
    collection: AsyncCollection = Depends(get_activities_collection),
    db: AsyncSession = Depends(get_db),
    s3_public_sign=Depends(get_s3_public_sign_client),
):
    return await activity_service.get_activity(
        activity_id, collection, db, s3_public_sign
    )


@router.patch(
    "/{activity_id}",
    response_model=ActivityResponse,
    status_code=status.HTTP_200_OK,
    summary="✏️ Update Activity (Partial Update)",
    description="""
    Refreshes the data. Send **only** the fields you want to update.
    *🚨 Important: This action is available only to the creator (`creator_id`) of this activity.*
    """,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid ID or empty payload (nothing to update)",
        },
        403: {
            "model": ErrorResponse,
            "description": "Forbidden: You are not the creator of this activity!",
        },
        404: {"model": ErrorResponse, "description": "No activity found"},
    },
)
async def update_activity(
    activity_id: str,
    activity_data: ActivityUpdate,
    collection: AsyncCollection = Depends(get_activities_collection),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    s3_public_sign=Depends(get_s3_public_sign_client),
):
    return await activity_service.update_activity(
        activity_id, activity_data, current_user, collection, db, s3_public_sign
    )


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(
    activity_id: str,
    current_user: User = Depends(get_current_user),
    collection: AsyncCollection = Depends(get_activities_collection),
):
    await activity_service.delete_activity(activity_id, current_user, collection)
