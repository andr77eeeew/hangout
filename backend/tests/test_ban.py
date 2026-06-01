from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, WebSocketException
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_current_user_ws
from app.main import app
from app.models.user import User, UserRole
from app.services.ban import BanService


class MockWebSocket:
    def __init__(self, query_params: dict[str, str]) -> None:
        self.query_params = query_params
        self.close_called = False
        self.close_code = None

    async def close(self, code: int = 1000) -> None:
        self.close_called = True
        self.close_code = code


@pytest.fixture
def override_auth_mod(mock_user: User) -> None:
    mock_user.id = 1
    mock_user.user_role = UserRole.moderator
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_ban_user_service_logic() -> None:
    db = AsyncMock(spec=AsyncSession)
    redis = AsyncMock(spec=Redis)

    moderator = User(id=1, user_role=UserRole.moderator, is_active=True)
    target_user = User(
        id=2,
        user_role=UserRole.client,
        is_active=True,
        is_banned=False,
        created_at=datetime.now(timezone.utc),
    )

    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = target_user
    db.execute.return_value = db_result

    with (
        patch(
            "app.services.auth.AuthService.revoke_all_user_sessions",
            new_callable=AsyncMock,
        ) as mock_revoke,
        patch(
            "app.core.ws_manager.connection_manager.disconnect_user_globally",
            new_callable=AsyncMock,
        ) as mock_disconnect_ws,
    ):
        banned = await BanService.ban_user(
            user_id=2,
            moderator=moderator,
            reason="Violation of Terms",
            db=db,
            redis=redis,
        )

        assert banned.is_banned is True
        db.add.assert_called_once_with(target_user)
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(target_user)
        mock_revoke.assert_called_once_with(redis, 2)
        mock_disconnect_ws.assert_called_once_with(
            user_id=2,
            code=4001,
            reason="Account banned",
        )


@pytest.mark.asyncio
async def test_ban_user_api_success(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_redis: AsyncMock,
    mock_user: User,
    override_auth_mod: None,
) -> None:
    target_user = User(
        id=2,
        email="bad@user.com",
        username="badguy",
        is_active=True,
        user_role=UserRole.client,
        is_banned=False,
        created_at=datetime.now(timezone.utc),
    )

    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = target_user
    mock_db.execute.return_value = db_result

    with (
        patch(
            "app.services.auth.AuthService.revoke_all_user_sessions",
            new_callable=AsyncMock,
        ) as mock_revoke,
        patch(
            "app.core.ws_manager.connection_manager.disconnect_user_globally",
            new_callable=AsyncMock,
        ) as mock_disconnect_ws,
    ):
        response = await async_client.post("/users/2/ban", json={"reason": "Spammer"})
        assert response.status_code == 200
        data = response.json()
        assert data["is_banned"] is True
        mock_db.commit.assert_called_once()
        mock_revoke.assert_called_once_with(mock_redis, 2)
        mock_disconnect_ws.assert_called_once_with(
            user_id=2,
            code=4001,
            reason="Account banned",
        )


@pytest.mark.asyncio
async def test_ban_moderator_forbidden(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_user: User,
    override_auth_mod: None,
) -> None:
    target_user = User(
        id=2,
        email="another_mod@user.com",
        username="another_mod",
        is_active=True,
        user_role=UserRole.moderator,
        is_banned=False,
        created_at=datetime.now(timezone.utc),
    )

    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = target_user
    mock_db.execute.return_value = db_result

    response = await async_client.post(
        "/users/2/ban", json={"reason": "Ban another mod"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot ban another moderator"


@pytest.mark.asyncio
async def test_ban_self_forbidden(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_user: User,
    override_auth_mod: None,
) -> None:
    response = await async_client.post("/users/1/ban", json={"reason": "Ban myself"})
    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot ban yourself"


@pytest.mark.asyncio
async def test_unban_user_api_success(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_user: User,
    override_auth_mod: None,
) -> None:
    target_user = User(
        id=2,
        email="bad@user.com",
        username="badguy",
        is_active=True,
        user_role=UserRole.client,
        is_banned=True,
        created_at=datetime.now(timezone.utc),
    )

    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = target_user
    mock_db.execute.return_value = db_result

    response = await async_client.post("/users/2/unban", json={"reason": "Forgiven"})
    assert response.status_code == 200
    data = response.json()
    assert data["is_banned"] is False
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_login_banned_user(async_client: AsyncClient, mock_db: AsyncMock) -> None:
    mock_result = MagicMock()
    from app.core.security import hash_password

    hashed = hash_password("Password123!")
    fake_user = User(
        id=1,
        email="test@mail.com",
        password=hashed,
        is_banned=True,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    mock_result.scalar_one_or_none.return_value = fake_user
    mock_db.execute.return_value = mock_result

    payload = {"email": "test@mail.com", "password": "Password123!"}
    response = await async_client.post("/user/login", json=payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "User is banned"


@pytest.mark.asyncio
async def test_login_unbanned_user_success(
    async_client: AsyncClient, mock_db: AsyncMock
) -> None:
    mock_result = MagicMock()
    from app.core.security import hash_password

    hashed = hash_password("Password123!")
    fake_user = User(
        id=1,
        email="test@mail.com",
        password=hashed,
        is_banned=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    mock_result.scalar_one_or_none.return_value = fake_user
    mock_db.execute.return_value = mock_result

    payload = {"email": "test@mail.com", "password": "Password123!"}
    response = await async_client.post("/user/login", json=payload)

    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_refresh_banned_user(async_client: AsyncClient) -> None:
    async_client.cookies.set("refresh_token", "fake-refresh-token")

    with patch(
        "app.services.auth.AuthService.verify_refresh_token",
        side_effect=HTTPException(
            status_code=401, detail="Could not validate credentials"
        ),
    ):
        response = await async_client.post("/user/refresh")

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.asyncio
async def test_get_current_user_dependency_rejects_banned_user() -> None:
    db = AsyncMock(spec=AsyncSession)

    with patch("jwt.decode") as mock_decode:
        mock_decode.return_value = {"type": "access", "sub": "10"}

        banned_user = User(id=10, is_active=True, is_banned=True)
        db_result = MagicMock()
        db_result.scalar_one_or_none.return_value = banned_user
        db.execute.return_value = db_result

        credentials = MagicMock()
        credentials.credentials = "fake-access-token"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials, db=db)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "User is banned"


@pytest.mark.asyncio
async def test_get_current_user_ws_dependency_rejects_banned_user() -> None:
    db = AsyncMock(spec=AsyncSession)

    with patch("jwt.decode") as mock_decode:
        mock_decode.return_value = {"type": "access", "sub": "10"}

        banned_user = User(id=10, is_active=True, is_banned=True)
        db_result = MagicMock()
        db_result.scalar_one_or_none.return_value = banned_user
        db.execute.return_value = db_result

        websocket = MockWebSocket(query_params={"token": "fake-ws-token"})

        with pytest.raises(WebSocketException) as exc_info:
            await get_current_user_ws(websocket=websocket, db=db)

        assert exc_info.value.code == 4001
        assert exc_info.value.reason == "User is banned"
        assert websocket.close_called is True
        assert websocket.close_code == 4001
