from unittest.mock import MagicMock
import pytest
from app.main import app

async def test_health(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

async def test_health_db_success(async_client, mock_db):
    mock_db.execute.return_value = None
    response = await async_client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"database": "connected"}

async def test_health_db_failure(async_client, mock_db):
    mock_db.execute.side_effect = Exception("DB error")
    response = await async_client.get("/health/db")
    assert response.status_code == 503
