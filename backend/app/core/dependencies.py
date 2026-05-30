import jwt
from fastapi import (
    Depends,
    HTTPException,
    Security,
    status,
    WebSocket,
    WebSocketException,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

http_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(http_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY.get_secret_value(), algorithms=["HS256"]
        )
    except PyJWTError:
        raise credentials_exception

    token_type = payload.get("type")
    if token_type != "access":
        raise credentials_exception
    sub = payload.get("sub")
    if sub is None:
        raise credentials_exception
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise credentials_exception
    stmt = (
        select(User).options(selectinload(User.favorite_tags)).where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_current_user_ws(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        raise WebSocketException(code=4001, reason="Token missing")

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY.get_secret_value(), algorithms=["HS256"]
        )
    except PyJWTError:
        await websocket.close(code=4001)
        raise WebSocketException(code=4001, reason="Invalid token")

    token_type = payload.get("type")
    if token_type != "access":
        await websocket.close(code=4001)
        raise WebSocketException(code=4001, reason="Invalid token type")

    sub = payload.get("sub")
    if sub is None:
        await websocket.close(code=4001)
        raise WebSocketException(code=4001, reason="Invalid user ID")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        await websocket.close(code=4001)
        raise WebSocketException(code=4001, reason="Invalid user ID")

    stmt = (
        select(User).options(selectinload(User.favorite_tags)).where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        await websocket.close(code=4001)
        raise WebSocketException(code=4001, reason="User inactive or not found")

    return user
