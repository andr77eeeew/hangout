from fastapi import HTTPException, status
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from pymongo.errors import PyMongoError
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from app.core.config import settings

_mongo_client: AsyncIOMotorClient | None = None
_mongo_db: AsyncIOMotorDatabase | None = None


async def init_mongo() -> None:
    global _mongo_client, _mongo_db

    _mongo_client = AsyncIOMotorClient(settings.MONGO_URL)
    _mongo_db = _mongo_client.get_default_database()

    try:
        await _mongo_db.command("ping")
    except PyMongoError:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
        raise


async def close_mongo():
    global _mongo_client, _mongo_db

    if _mongo_client is not None:
        _mongo_client.close()

    _mongo_client = None
    _mongo_db = None


async def get_mongo_db() -> AsyncIOMotorDatabase:
    if _mongo_db is None:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mongo DB is unavailable",
        )
    return _mongo_db


async def get_activities_collection() -> AsyncIOMotorCollection:
    db = await get_mongo_db()
    return db["activities"]