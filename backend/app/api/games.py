from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis

from app.core.redis_client import get_redis
from app.schemas.game import GameSearchResponse
from app.services.game_search import GameSearchService

router = APIRouter(prefix="/games", tags=["🎮 Games"])


@router.get(
    "/search",
    response_model=GameSearchResponse,
    summary="Search for games using autocomplete",
    description="""
               Proxies searches to the RAWG API with caching in Redis (TTL: 2 hours).

               **Rules for frontend calls:**
               - Apply a **300-500ms** debounce to each keystroke
               - Do not send requests if `q` is shorter than 2 characters
               - If `results: []`, display the message “Enter the name manually”
               """,
)
async def search_games(
    q: str = Query(
        ..., min_length=1, description="Search query, for example: 'Minecraft'"
    ),
    redis: Redis = Depends(get_redis),
):
    result, is_cached = await GameSearchService.search_games(q, redis)
    return GameSearchResponse(results=result, cached=is_cached)
