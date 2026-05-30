from unittest.mock import AsyncMock, MagicMock, patch
import json
import httpx

from app.core.config import settings
from app.schemas.game import GameSearchResult
from app.services.game_search import GameSearchService


async def test_search_games_query_too_short() -> None:
    mock_redis = AsyncMock()
    results, ok = await GameSearchService.search_games(" a ", mock_redis)
    assert results == []
    assert not ok
    mock_redis.get.assert_not_called()


async def test_search_games_cache_hit() -> None:
    mock_redis = AsyncMock()

    # Prepare cached JSON data
    cached_data = [
        {
            "rawg_id": 123,
            "name": "Witcher 3",
            "slug": "witcher-3",
            "cover_url": "https://example.com/witcher3.jpg",
        }
    ]
    mock_redis.get.return_value = json.dumps(cached_data)

    results, ok = await GameSearchService.search_games("witcher", mock_redis)

    assert ok
    assert len(results) == 1
    assert isinstance(results[0], GameSearchResult)
    assert results[0].rawg_id == 123
    assert results[0].name == "Witcher 3"

    mock_redis.get.assert_called_once_with("games:search:witcher")


async def test_search_games_missing_api_key() -> None:
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    with patch.object(settings, "RAWG_API_KEY", None):
        results, ok = await GameSearchService.search_games("witcher", mock_redis)
        assert results == []
        assert not ok


async def test_search_games_cache_miss_api_success() -> None:
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    rawg_response = {
        "results": [
            {
                "id": 456,
                "name": "Cyberpunk 2077",
                "slug": "cyberpunk-2077",
                "background_image": "https://example.com/cp2077.jpg",
            }
        ]
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = rawg_response
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    with (
        patch.object(settings, "RAWG_API_KEY", "test-api-key"),
        patch("app.services.game_search.get_http_client", return_value=mock_client),
    ):
        results, ok = await GameSearchService.search_games("cyberpunk", mock_redis)

        assert ok
        assert len(results) == 1
        assert results[0].rawg_id == 456
        assert results[0].name == "Cyberpunk 2077"

        # Verify it was saved to the Redis cache
        mock_redis.setex.assert_called_once()
        cache_key, ttl, serialized = mock_redis.setex.call_args[0]
        assert cache_key == "games:search:cyberpunk"
        assert ttl == GameSearchService.CACHE_TTL_SECONDS
        parsed_cache = json.loads(serialized)
        assert parsed_cache[0]["rawg_id"] == 456


async def test_search_games_cache_miss_api_failure() -> None:
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.HTTPError("API offline")

    with (
        patch.object(settings, "RAWG_API_KEY", "test-api-key"),
        patch("app.services.game_search.get_http_client", return_value=mock_client),
    ):
        results, ok = await GameSearchService.search_games("cyberpunk", mock_redis)

        assert results == []
        assert not ok
        mock_redis.setex.assert_not_called()
