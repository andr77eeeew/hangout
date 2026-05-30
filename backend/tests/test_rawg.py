from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from bson import ObjectId
from PIL import Image

from app.core.config import settings
from app.tasks.rawg import (
    async_fetch_game_cover,
    fetch_game_cover,
    update_activity_cover,
    fail_activity_cover,
)


@pytest.mark.asyncio
async def test_update_activity_cover() -> None:
    mock_coll = AsyncMock()
    activity_id = str(ObjectId())

    await update_activity_cover(activity_id, "covers/test.webp", 100, mock_coll)

    mock_coll.update_one.assert_called_once_with(
        {"_id": ObjectId(activity_id), "category": "games"},
        {
            "$set": {
                "extra_data.cover_key": "covers/test.webp",
                "extra_data.cover_status": "ready",
                "extra_data.game_id": 100,
            }
        },
    )


@pytest.mark.asyncio
async def test_fail_activity_cover() -> None:
    mock_coll = AsyncMock()
    activity_id = str(ObjectId())

    await fail_activity_cover(activity_id, mock_coll)

    mock_coll.update_one.assert_called_once_with(
        {"_id": ObjectId(activity_id), "category": "games"},
        {"$set": {"extra_data.cover_status": "failed"}},
    )


@pytest.mark.asyncio
async def test_async_fetch_game_cover_cached() -> None:
    mock_activities = AsyncMock()
    mock_covers = AsyncMock()

    cached_doc = {
        "game_name": "Minecraft",
        "cover_status": "ready",
        "cover_key": "covers/games/123.webp",
        "game_id": 123,
    }
    mock_covers.find_one.return_value = cached_doc

    activity_id = str(ObjectId())

    with (
        patch("app.tasks.rawg.get_activities_collection", return_value=mock_activities),
        patch("app.tasks.rawg.get_game_covers_collection", return_value=mock_covers),
    ):
        res = await async_fetch_game_cover(activity_id, "Minecraft")

        assert res["status"] == "cached"
        assert res["cover_key"] == "covers/games/123.webp"

        mock_covers.find_one.assert_called_once_with({"game_name": "Minecraft"})
        mock_activities.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_game_cover_no_api_key() -> None:
    mock_activities = AsyncMock()
    mock_covers = AsyncMock()
    mock_covers.find_one.return_value = None

    activity_id = str(ObjectId())

    with (
        patch("app.tasks.rawg.get_activities_collection", return_value=mock_activities),
        patch("app.tasks.rawg.get_game_covers_collection", return_value=mock_covers),
        patch.object(settings, "RAWG_API_KEY", None),
    ):
        res = await async_fetch_game_cover(activity_id, "Minecraft")

        assert res["status"] == "failed"
        assert res["reason"] == "No RAWG_API_KEY"
        mock_activities.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_game_cover_success() -> None:
    mock_activities = AsyncMock()
    mock_covers = AsyncMock()
    mock_covers.find_one.return_value = None

    activity_id = str(ObjectId())

    # Mock RAWG game details response
    rawg_body = {
        "results": [
            {
                "id": 789,
                "slug": "portal-2",
                "background_image": "https://example.com/portal2.jpg",
            }
        ]
    }

    mock_resp_rawg = MagicMock(spec=httpx.Response)
    mock_resp_rawg.json.return_value = rawg_body
    mock_resp_rawg.raise_for_status = MagicMock()

    # Mock background image content response
    mock_resp_img = MagicMock(spec=httpx.Response)
    mock_resp_img.content = b"fake-image-bytes"
    mock_resp_img.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = [mock_resp_rawg, mock_resp_img]
    mock_client.__aenter__.return_value = mock_client

    # Mock S3 uploading
    mock_s3 = MagicMock()
    mock_s3.put_object = MagicMock()

    # Mock PIL Image processing to avoid loading real image bytes
    mock_image = MagicMock(spec=Image.Image)
    mock_image.thumbnail = MagicMock()
    mock_image.save = MagicMock()

    with (
        patch("app.tasks.rawg.get_activities_collection", return_value=mock_activities),
        patch("app.tasks.rawg.get_game_covers_collection", return_value=mock_covers),
        patch("app.tasks.rawg.get_s3_client", return_value=mock_s3),
        patch("httpx.AsyncClient", return_value=mock_client),
        patch("PIL.Image.open", return_value=mock_image),
        patch.object(settings, "RAWG_API_KEY", "test-key"),
        patch.object(settings, "BUCKET_NAME", "test-bucket"),
    ):
        res = await async_fetch_game_cover(activity_id, "Portal 2")

        assert res["status"] == "fetched"
        assert res["cover_key"] == "covers/games/789.webp"

        mock_covers.update_one.assert_called_once()
        mock_activities.update_one.assert_called_once()
        mock_s3.put_object.assert_called_once()


def test_fetch_game_cover_wrapper() -> None:
    activity_id = str(ObjectId())

    # We mock async_fetch_game_cover since it is called inside the task's event loop
    with (
        patch(
            "app.tasks.rawg.async_fetch_game_cover", new_callable=AsyncMock
        ) as mock_async,
        patch("app.tasks.rawg.init_mongo", new_callable=AsyncMock) as mock_init,
        patch("app.tasks.rawg.close_mongo", new_callable=AsyncMock) as mock_close,
    ):
        mock_async.return_value = {"status": "cached"}

        res = fetch_game_cover(activity_id, "Minecraft")

        assert res == {"status": "cached"}
        mock_init.assert_called_once()
        mock_close.assert_called_once()
        mock_async.assert_called_once_with(activity_id, "Minecraft")
