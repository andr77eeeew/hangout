from fastapi import HTTPException
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from app.core.config import settings

_mongo_client: AsyncMongoClient | None = None
_mongo_db: AsyncDatabase | None = None


async def init_mongo() -> None:
    global _mongo_client, _mongo_db

    if not settings.MONGO_URL:
        raise RuntimeError("MONGO_URL is not configured")

    _mongo_client = AsyncMongoClient(settings.MONGO_URL, tz_aware=True)
    _mongo_db = _mongo_client.get_default_database()

    try:
        await _mongo_db.command("ping")
    except PyMongoError:
        await _mongo_client.aclose()
        _mongo_client = None
        _mongo_db = None
        raise


async def close_mongo():
    global _mongo_client, _mongo_db

    if _mongo_client is not None:
        await _mongo_client.aclose()

    _mongo_client = None
    _mongo_db = None


async def get_mongo_db() -> AsyncDatabase:
    if _mongo_db is None:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mongo DB is unavailable",
        )
    return _mongo_db


async def get_activities_collection() -> AsyncCollection:
    db = await get_mongo_db()
    return db["activities"]


async def get_membership_collection() -> AsyncCollection:
    db = await get_mongo_db()
    return db["membership"]