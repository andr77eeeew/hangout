from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from app.core.dependencies import get_current_user
from app.main import app

@pytest.fixture(autouse=True)
def override_auth(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def test_get_feed_success(async_client, mock_mongo):
    # Мокаем красивый ответ от MongoDB
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[
        {
            "_id": "60d5ec49c4f1c9a6f81a1b3a",
            "title": "Test Activity",
            "description": "Very long test description goes here",
            "type": "open",
            "format": "online",
            "category": "games",
            "date": "2026-10-10T12:00:00Z",
            "max_members": 10,
            "creator_id": 1,
            "status": "active",
            "members": [],
            "tags": ["test_tag"],
            "created_at": "2026-04-01T12:00:00Z",
            "updated_at": "2026-04-01T12:00:00Z",
            "current_members": 0,
        }
    ])
    mock_mongo.find = MagicMock(return_value=mock_cursor)

    # Патчим _fetch_users_map чтобы не делать лишний мок PostgreSQL внутри
    with patch(
        "app.services.activity.ActivityService._fetch_users_map",
        return_value={1: MagicMock(_id=1, username="testuser", avatar="avatars/test.jpg")},
    ):
        response = await async_client.get("/activities/feed?limit=10")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Test Activity"
    assert "next_cursor" in data


async def test_get_activity_not_found(async_client, mock_mongo):
    # Имитируем что база ничего не нашла
    mock_mongo.find_one.return_value = None

    response = await async_client.get("/activities/60d5ec49c4f1c9a6f81a1b3a")
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


async def test_create_activity_invalid_date(async_client):
    # Умышленно передаем дату в прошлом
    payload = {
        "title": "Valid Title Here",
        "description": "Valid description length over here",
        "type": "open",
        "format": "online",
        "category": "games",
        "date": "2020-01-01T12:00:00Z",  # <-- Ошибка (в прошлом)
        "max_members": 5,
        "tags": ["cool"],
    }

    response = await async_client.post("/activities/", json=payload)

    assert response.status_code == 422
    assert "Date and time must be in the future" in str(response.json())


async def test_create_activity_success(async_client, mock_db, mock_mongo):
    payload = {
        "title": "Valid Title Here",
        "description": "Valid description length over here",
        "type": "open",
        "format": "online",
        "category": "games",
        "date": "2026-10-10T12:00:00Z",
        "max_members": 5,
        "tags": ["cool"],
    }
    with patch("app.services.activity.ActivityService.create_activity") as mock_create:
        mock_create.return_value = {**payload, "_id": "fake-id", "creator_id": 1, "status": "active", "created_at": "2026-04-01T12:00:00Z", "updated_at": "2026-04-01T12:00:00Z", "members": [], "current_members": 0}
        response = await async_client.post("/activities/", json=payload)
    
    assert response.status_code == 201
    assert response.json()["_id"] == "fake-id"

async def test_get_activity_success(async_client, mock_mongo):
    with patch("app.services.activity.ActivityService.get_activity") as mock_get:
        mock_get.return_value = {"_id": "fake-id", "title": "Test Title", "description": "Long enough description", "type": "open", "format": "online", "category": "games", "date": "2026-10-10T12:00:00Z", "max_members": 5, "tags": ["cool"], "creator_id": 1, "status": "active", "created_at": "2026-04-01T12:00:00Z", "updated_at": "2026-04-01T12:00:00Z", "members": [], "current_members": 0}
        response = await async_client.get("/activities/fake-id")
        
    assert response.status_code == 200
    assert response.json()["_id"] == "fake-id"

async def test_update_activity_success(async_client, mock_mongo, mock_db):
    payload = {"title": "Updated Title"}
    with patch("app.services.activity.ActivityService.update_activity") as mock_update:
        mock_update.return_value = {"_id": "fake-id", "title": "Updated Title", "description": "Long enough description", "type": "open", "format": "online", "category": "games", "date": "2026-10-10T12:00:00Z", "max_members": 5, "tags": ["cool"], "creator_id": 1, "status": "active", "created_at": "2026-04-01T12:00:00Z", "updated_at": "2026-04-01T12:00:00Z", "members": [], "current_members": 0}
        response = await async_client.patch("/activities/fake-id", json=payload)
        
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"

async def test_delete_activity_success(async_client, mock_mongo):
    with patch("app.services.activity.ActivityService.delete_activity") as mock_delete:
        mock_delete.return_value = None
        response = await async_client.delete("/activities/fake-id")
        
    assert response.status_code == 204
