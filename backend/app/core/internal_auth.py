import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from app.core.config import settings

internal_api_key_header = APIKeyHeader(name="X-Internal-Key", auto_error=False)


async def verify_internal_api_key(
    api_key: str | None = Depends(internal_api_key_header),
) -> None:
    expected = settings.INTERNAL_API_KEY.get_secret_value()
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal API key",
        )
