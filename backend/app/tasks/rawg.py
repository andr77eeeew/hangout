import asyncio
import io
import urllib.parse
from datetime import datetime, timezone

import httpx
from bson import ObjectId
from celery import Task
from PIL import Image
from pymongo.errors import DuplicateKeyError

from app.core.celery_config import celery_app
from app.core.config import settings
from app.core.mongo import get_activities_collection, get_game_covers_collection
from app.core.storage import get_s3_client


async def async_fetch_game_cover(activity_id: str, game_name: str):
    activities = await get_activities_collection()
    covers = await get_game_covers_collection()

    cached = await covers.find_one({"game_name": game_name})
    if cached and cached.get("cover_status") == "ready":
        await update_activity_cover(
            activity_id, cached["cover_key"], cached["game_id"], activities
        )
        return {"status": "cached", "cover_key": cached["cover_key"]}

    if not settings.RAWG_API_KEY:
        await fail_activity_cover(activity_id, activities)
        return {"status": "failed", "reason": "No RAWG_API_KEY"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        encoded_name = urllib.parse.quote(game_name)
        url = f"https://api.rawg.io/api/games?key={settings.RAWG_API_KEY}&search={encoded_name}&page_size=1"
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        if not data.get("results"):
            await fail_activity_cover(activity_id, activities)
            return {"status": "failed", "reason": "Game not found"}

        game_data = data["results"][0]
        image_url = game_data.get("background_image")

        if not image_url:
            await fail_activity_cover(activity_id, activities)
            return {"status": "failed", "reason": "No background image"}

        img_response = await client.get(image_url)
        img_response.raise_for_status()
        img_bytes = img_response.content

    loop = asyncio.get_running_loop()

    def process_image():
        image = Image.open(io.BytesIO(img_bytes))
        image.thumbnail((1000, 1000))
        out_io = io.BytesIO()
        image.save(out_io, format="WEBP", quality=85)
        out_io.seek(0)
        return out_io.getvalue()

    processed_bytes = await loop.run_in_executor(None, process_image)

    game_slug = game_data.get("slug", "unknown")
    game_id = game_data.get("id")
    object_key = f"covers/games/{game_id}.webp"

    s3_client = get_s3_client()

    def upload_to_s3():
        s3_client.put_object(
            Bucket=settings.BUCKET_NAME,
            Key=object_key,
            Body=processed_bytes,
            ContentType="image/webp",
        )

    await loop.run_in_executor(None, upload_to_s3)

    try:
        await covers.update_one(
            {"game_id": game_id},
            {
                "$set": {
                    "game_name": game_name,
                    "game_slug": game_slug,
                    "cover_key": object_key,
                    "rawg_url": image_url,
                    "cover_status": "ready",
                    "fetched_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except DuplicateKeyError:
        pass

    await update_activity_cover(activity_id, object_key, game_id, activities)
    return {"status": "fetched", "cover_key": object_key}


async def update_activity_cover(
    activity_id: str, cover_key: str, game_id: int, collection
):
    await collection.update_one(
        {"_id": ObjectId(activity_id), "category": "games"},
        {
            "$set": {
                "extra_data.cover_key": cover_key,
                "extra_data.cover_status": "ready",
                "extra_data.game_id": game_id,
            }
        },
    )


async def fail_activity_cover(activity_id: str, collection):
    await collection.update_one(
        {"_id": ObjectId(activity_id), "category": "games"},
        {"$set": {"extra_data.cover_status": "failed"}},
    )


@celery_app.task(bind=True, max_retries=3)
def fetch_game_cover(self: Task, activity_id: str, game_name: str):
    async def runner():
        from app.core.mongo import close_mongo, init_mongo

        await init_mongo()
        try:
            return await async_fetch_game_cover(activity_id, game_name)
        finally:
            await close_mongo()

    try:
        return asyncio.run(runner())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries)
