import os

import pytest

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost/testdb"
os.environ["MONGO_URL"] = "mongodb://localhost:27017/testdb"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["SECRET_KEY"] = "test_secret_key_which_is_long_enough_for_hs256"
os.environ["BUCKET_USER"] = "testuser"
os.environ["BUCKET_PASSWORD"] = "testpassword"
os.environ["BUCKET_NAME"] = "testbucket"
os.environ["BUCKET_ENDPOINT_URL"] = "http://localhost:9000"
os.environ["BUCKET_PUBLIC_URL"] = "http://localhost:9000"

from unittest.mock import AsyncMock, MagicMock

from app.core.database import get_db
from app.core.mongo import get_activities_collection
from app.core.redis_client import get_redis
from app.core.storage import get_s3_client, get_s3_public_sign_client
from app.main import app
from app.models.user import User
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_db():
    mock = AsyncMock()
    mock.add = MagicMock()
    return mock
    


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    pipe = AsyncMock()
    pipe.set = MagicMock(return_value=pipe)
    pipe.sadd = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    mock.pipeline = MagicMock()
    mock.pipeline.return_value.__aenter__.return_value = pipe
    return mock


@pytest.fixture
def mock_mongo():
    return AsyncMock()


@pytest.fixture
def mock_s3():
    return MagicMock()


@pytest.fixture
def mock_s3_sign():
    mock = MagicMock()
    mock.generate_presigned_url.return_value = "http://fake-s3-url/image.jpg"
    return mock


@pytest.fixture
def mock_user():
    from datetime import datetime, timezone
    return User(
        id=1,
        email="test@user.com",
        username="testuser",
        is_active=True,
        password="hashed_password",
        avatar="avatars/test.jpg",
        banner=None,
        created_at=datetime.now(timezone.utc)
    )


@pytest.fixture
async def async_client(mock_db, mock_redis, mock_mongo, mock_s3, mock_s3_sign):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_activities_collection] = lambda: mock_mongo
    app.dependency_overrides[get_s3_client] = lambda: mock_s3
    app.dependency_overrides[get_s3_public_sign_client] = lambda: mock_s3_sign

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client

    app.dependency_overrides.clear()
