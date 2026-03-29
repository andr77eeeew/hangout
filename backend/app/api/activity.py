from fastapi import APIRouter, Depends
from pymongo.asynchronous.collection import AsyncCollection
from starlette import status

from app.core.dependencies import get_current_user
from app.core.mongo import get_activities_collection
from app.models.user import User
from app.schemas.activity import ActivityResponse, ActivityCreate
from app.services.activity import ActivityService

router = APIRouter(prefix="/activities", tags=["activity"])
activity_service = ActivityService()


@router.post("/", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    activity_data: ActivityCreate,
    current_user: User = Depends(get_current_user),
    collection: AsyncCollection = Depends(get_activities_collection),
):
    return await activity_service.create_activity(
        activity_data=activity_data,
        creator_id=current_user.id,
        collection=collection,
    )