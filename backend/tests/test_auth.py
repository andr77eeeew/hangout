from unittest.mock import MagicMock, patch

from app.core.security import hash_password
from app.models.user import User
from sqlalchemy.exc import IntegrityError


async def test_register_success(async_client, mock_db):
    payload = {
        "email": "new@mail.com",
        "username": "newuser",
        "password": "Password123!",
    }

    from datetime import datetime, timezone
    async def mock_refresh(obj):
        obj.id = 1
        obj.created_at = datetime.now(timezone.utc)
    mock_db.refresh.side_effect = mock_refresh
    mock_db.commit.return_value = None  # Мокаем успешный коммит

    response = await async_client.post("/user/register", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == "new@mail.com"
    assert data["username"] == "newuser"


async def test_register_email_conflict(async_client, mock_db):
    payload = {
        "email": "test@mail.com",
        "username": "testuser",
        "password": "Password123!",
    }

    # Имитируем ошибку уникальности в БД (email занят)
    class FakeOrig:
        def __str__(self):
            return "duplicate key value violates unique constraint 'ix_users_email'"

    mock_db.flush.side_effect = IntegrityError("statement", "params", FakeOrig())

    response = await async_client.post("/user/register", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


async def test_login_success(async_client, mock_db, mock_redis):
    mock_result = MagicMock()
    hashed = hash_password("Password123!")
    fake_user = User(id=1, email="test@mail.com", password=hashed)
    mock_result.scalar_one_or_none.return_value = fake_user
    mock_db.execute.return_value = mock_result

    payload = {"email": "test@mail.com", "password": "Password123!"}
    response = await async_client.post("/user/login", json=payload)

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.cookies


async def test_login_wrong_password(async_client, mock_db):
    mock_result = MagicMock()
    hashed = hash_password("Password123!")  # Верный пароль юзера
    fake_user = User(id=1, email="test@mail.com", password=hashed)
    mock_result.scalar_one_or_none.return_value = fake_user
    mock_db.execute.return_value = mock_result

    payload = {"email": "test@mail.com", "password": "WrongPassword!"}
    response = await async_client.post("/user/login", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


async def test_logout(async_client, mock_redis):
    # Устанавливаем куку так, как будто мы залогинены
    async_client.cookies.set("refresh_token", "fake-token")

    # Так как подпись JWT требует SECRET_KEY, здесь мы делаем локальный патч метода верификации
    with patch(
        "app.services.auth.AuthService.verify_refresh_token",
        return_value=(User(id=1), "fake-jti"),
    ):
        response = await async_client.post("/user/logout")

    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"
    assert not response.cookies.get("refresh_token")

async def test_refresh_success(async_client, mock_redis, mock_db):
    async_client.cookies.set("refresh_token", "fake-refresh-token")
    
    with patch(
        "app.services.auth.AuthService.verify_refresh_token",
        return_value=(User(id=1), "old_jti"),
    ), patch(
        "app.services.auth.AuthService.consume_refresh_session",
        return_value=True,
    ), patch(
        "app.services.auth.AuthService.store_refresh_session",
        return_value=None,
    ):
        response = await async_client.post("/user/refresh")

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.cookies

async def test_refresh_no_cookie(async_client):
    response = await async_client.post("/user/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"
