from unittest.mock import MagicMock

import pytest
from app.core.dependencies import get_current_user
from app.main import app


@pytest.fixture(autouse=True)
def override_auth(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def test_get_me(async_client, mock_user):
    response = await async_client.get("/user/me")
    assert response.status_code == 200
    assert response.json()["email"] == mock_user.email
    assert response.json()["username"] == mock_user.username
    assert response.json()["avatar"] == "http://fake-s3-url/image.jpg"  # Мокнутый S3


async def test_update_me_success(async_client, mock_db, mock_user):
    payload = {"username": "newusername"}

    # Мокаем проверку на существование (пользователя с таким юзернеймом нет)
    mock_result_empty = MagicMock()
    mock_result_empty.scalar_one_or_none.return_value = None

    mock_result_user = MagicMock()
    mock_user.username = "newusername"
    mock_result_user.scalar_one.return_value = mock_user

    mock_db.execute.side_effect = [mock_result_empty, None, mock_result_user]

    response = await async_client.patch("/user/me", json=payload)

    assert response.status_code == 200
    assert response.json()["username"] == "newusername"


async def test_update_me_nothing_to_update(async_client):
    response = await async_client.patch("/user/me", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "Nothing to Update"

async def test_update_password(async_client, mock_db, mock_user):
    payload = {"old_password": "OldPassword123!", "new_password": "NewPassword123!", "confirm_password": "NewPassword123!"}
    from unittest.mock import patch
    with patch("app.services.profile.ProfileService.update_password") as mock_update:
        mock_update.return_value = None
        response = await async_client.patch("/user/password", json=payload)
        
    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"

async def test_update_avatar(async_client, mock_db):
    from unittest.mock import patch
    files = {"file": ("avatar.jpg", b"fake image content", "image/jpeg")}
    with patch("app.services.profile.ProfileService.upload_avatar") as mock_upload:
        fake_user = MagicMock()
        mock_upload.return_value = fake_user
        
        with patch("app.services.profile.ProfileService.to_user_response") as mock_resp:
            mock_resp.return_value = {"id": 1, "email": "test@mail.com", "username": "testuser", "bio": None, "links": {}, "avatar": "http://fake-s3/avatar.jpg", "banner": None, "created_at": "2026-04-01T12:00:00Z"}
            response = await async_client.patch("/user/avatar", files=files)
            
    assert response.status_code == 200
    assert response.json()["avatar"] == "http://fake-s3/avatar.jpg"

async def test_update_banner(async_client, mock_db):
    from unittest.mock import patch
    files = {"file": ("banner.jpg", b"fake image content", "image/jpeg")}
    with patch("app.services.profile.ProfileService.upload_banner") as mock_upload:
        fake_user = MagicMock()
        mock_upload.return_value = fake_user
        
        with patch("app.services.profile.ProfileService.to_user_response") as mock_resp:
            mock_resp.return_value = {"id": 1, "email": "test@mail.com", "username": "testuser", "bio": None, "links": {}, "avatar": None, "banner": "http://fake-s3/banner.jpg", "created_at": "2026-04-01T12:00:00Z"}
            response = await async_client.patch("/user/banner", files=files)
            
    assert response.status_code == 200
    assert response.json()["banner"] == "http://fake-s3/banner.jpg"
