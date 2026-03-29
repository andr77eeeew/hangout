from datetime import datetime, timezone

from pymongo.asynchronous.collection import AsyncCollection

from app.schemas.activity import ActivityCreate, ActivityResponse, ActivityStatus


class ActivityService:
    @staticmethod
    async def create_activity(
        activity_data: ActivityCreate, creator_id: int, collection: AsyncCollection
    ) -> ActivityResponse:
        now = datetime.now(timezone.utc)

        activity_dict = activity_data.model_dump()
        activity_dict["creator_id"] = creator_id
        activity_dict["current_members"] = 1
        activity_dict["status"] = ActivityStatus.active.value
        activity_dict["created_at"] = now
        activity_dict["updated_at"] = now

        result = await collection.insert_one(activity_dict)
        created_activity = await collection.find_one({"_id": result.inserted_id})

        return ActivityResponse(**created_activity)