import json

import httpx
from redis.asyncio import Redis

from app.core.config import settings
from app.schemas.game import GameSearchResult


class GameSearchService:
    CACHE_TTL_SECONDS = 60 * 60 * 2
    MIN_QUERY_LENGTH = 2
    RAWG_PAGE_SIZE = 8

    @staticmethod
    def _build_cache_key(query: str) -> str:
        normalized = query.strip().lower()
        return f"games:search:{normalized}"

    @staticmethod
    def _parse_rawg_result(data: dict) -> list[GameSearchResult]:
        results = []
        for game in data.get("results", []):
            results.append(
                GameSearchResult(
                    rawg_id=game["id"],
                    name=game["name"],
                    slug=game["slug"],
                    cover_url=game.get("background_image"),
                )
            )
        return results

    @staticmethod
    async def search_games(
        query: str,
        redis: Redis,
    ) -> tuple[list[GameSearchResult], bool]:
        if len(query.strip()) < GameSearchService.MIN_QUERY_LENGTH:
            return [], False

        cache_key = GameSearchService._build_cache_key(query)

        cached_raw = await redis.get(cache_key)
        if cached_raw:
            cached_list = json.loads(cached_raw)
            return [GameSearchResult(**item) for item in cached_list], True

        if not settings.RAWG_API_KEY:
            return [], False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.rawg.io/api/games",
                    params={
                        "key": settings.RAWG_API_KEY,
                        "search": query.strip(),
                        "page_size": GameSearchService.RAWG_PAGE_SIZE,
                        "search_precise": True,
                    },
                )
                response.raise_for_status()
                data = response.json()

        except (httpx.Timeout, httpx.HTTPError):
            return [], False

        results = GameSearchService._parse_rawg_result(data)

        if results:
            serialized = json.dumps([r.model_dump() for r in results])
            await redis.setex(
                cache_key, GameSearchService.CACHE_TTL_SECONDS, serialized
            )

        return results, True
