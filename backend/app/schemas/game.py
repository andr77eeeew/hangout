from pydantic import BaseModel


class GameSearchResult(BaseModel):
    rawg_id: int
    name: str
    slug: str
    cover_url: str | None


class GameSearchResponse(BaseModel):
    results: list[GameSearchResult]
    cached: bool
