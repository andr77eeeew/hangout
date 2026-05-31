import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from app.tasks.notifications import async_notify_tag_matching_users
from app.models.user import User
from app.models.tags import Tag
from app.services.notification import NotificationService


class MockCursor:
    def __init__(self, data: list[dict]) -> None:
        self.data = data

    async def to_list(self, length: int) -> list[dict]:
        return self.data


@pytest.mark.asyncio
async def test_async_notify_tag_matching_users_success() -> None:
    activity_id = ObjectId()
    activity = {
        "_id": activity_id,
        "title": "Board Game Night",
        "creator_id": 99,
        "tags": ["Board Games", "Fun"],
    }

    # Mock MongoDB activities collection
    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = activity

    # Mock PostgreSQL Database connection
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    # Query 1: Tag IDs select
    mock_tag_result = MagicMock()
    mock_tag_result.scalars.return_value.all.return_value = [10, 11]

    # Query 2: Users select
    user1 = User(
        id=100,
        telegram_id="123456",
        is_active=True,
    )
    # Mock relationship attributes since they are lazy or loaded
    user1.favorite_tags = [
        Tag(id=10, name="Board Games", slug="board-games"),
        Tag(id=20, name="Chess", slug="chess"),
    ]

    user2 = User(
        id=101,
        telegram_id="789012",
        is_active=True,
    )
    user2.favorite_tags = [
        Tag(id=11, name="Fun", slug="fun"),
        Tag(id=30, name="Hiking", slug="hiking"),
    ]

    user3 = User(
        id=102,
        telegram_id="345678",
        is_active=True,
    )
    user3.favorite_tags = [
        Tag(id=10, name="Board Games", slug="board-games"),
        Tag(id=11, name="Fun", slug="fun"),
    ]

    mock_user_result = MagicMock()
    mock_user_result.scalars.return_value.all.return_value = [user1, user2, user3]

    # Use a real async function to mock execute
    db_calls = []

    async def mock_execute(stmt):
        db_calls.append(stmt)
        if len(db_calls) == 1:
            return mock_tag_result
        return mock_user_result

    mock_db.execute = mock_execute

    with (
        patch(
            "app.tasks.notifications.get_activities_collection",
            return_value=mock_activities_col,
        ),
        patch("app.tasks.notifications.AsyncSessionLocal", return_value=mock_db),
        patch.object(NotificationService, "notify_tag_match") as mock_notify,
    ):
        await async_notify_tag_matching_users(str(activity_id))

        # Check that notify_tag_match was called for the three matched users with correct tags
        assert mock_notify.call_count == 3

        # Match calls
        called_args = [call.kwargs for call in mock_notify.call_args_list]

        # User 1 matches "Board Games"
        user1_call = next(c for c in called_args if c["user_id"] == 100)
        assert user1_call["activity_title"] == "Board Game Night"
        assert user1_call["matched_tags"] == ["Board Games"]

        # User 2 matches "Fun"
        user2_call = next(c for c in called_args if c["user_id"] == 101)
        assert user2_call["activity_title"] == "Board Game Night"
        assert user2_call["matched_tags"] == ["Fun"]

        # User 3 matches both "Board Games" and "Fun"
        user3_call = next(c for c in called_args if c["user_id"] == 102)
        assert user3_call["activity_title"] == "Board Game Night"
        assert set(user3_call["matched_tags"]) == {"Board Games", "Fun"}


@pytest.mark.asyncio
async def test_async_notify_tag_matching_users_no_tags() -> None:
    activity_id = ObjectId()
    activity = {
        "_id": activity_id,
        "title": "Board Game Night",
        "creator_id": 99,
        "tags": [],
    }

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = activity
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    with (
        patch(
            "app.tasks.notifications.get_activities_collection",
            return_value=mock_activities_col,
        ),
        patch("app.tasks.notifications.AsyncSessionLocal", return_value=mock_db),
    ):
        await async_notify_tag_matching_users(str(activity_id))
        mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_async_notify_tag_matching_users_no_matching_tags_in_db() -> None:
    activity_id = ObjectId()
    activity = {
        "_id": activity_id,
        "title": "Board Game Night",
        "creator_id": 99,
        "tags": ["UnusedTag"],
    }

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = activity

    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    mock_tag_result = MagicMock()
    mock_tag_result.scalars.return_value.all.return_value = []

    async def mock_execute(stmt):
        return mock_tag_result

    mock_db.execute = mock_execute

    with (
        patch(
            "app.tasks.notifications.get_activities_collection",
            return_value=mock_activities_col,
        ),
        patch("app.tasks.notifications.AsyncSessionLocal", return_value=mock_db),
    ):
        await async_notify_tag_matching_users(str(activity_id))


@pytest.mark.asyncio
async def test_async_notify_tag_matching_users_query_filters() -> None:
    activity_id = ObjectId()
    activity = {
        "_id": activity_id,
        "title": "Board Game Night",
        "creator_id": 99,
        "tags": ["Board Games"],
    }

    mock_activities_col = AsyncMock()
    mock_activities_col.find_one.return_value = activity

    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    mock_tag_result = MagicMock()
    mock_tag_result.scalars.return_value.all.return_value = [10]

    mock_user_result = MagicMock()
    mock_user_result.scalars.return_value.all.return_value = []

    db_calls = []

    async def mock_execute(stmt):
        db_calls.append(stmt)
        if len(db_calls) == 1:
            return mock_tag_result
        return mock_user_result

    mock_db.execute = mock_execute

    with (
        patch(
            "app.tasks.notifications.get_activities_collection",
            return_value=mock_activities_col,
        ),
        patch("app.tasks.notifications.AsyncSessionLocal", return_value=mock_db),
    ):
        await async_notify_tag_matching_users(str(activity_id))

        assert len(db_calls) == 2

        # Verify the structure/filters of the second query
        user_query_stmt = db_calls[1]
        sql_query_str = str(user_query_stmt)

        # 1. Joins UserTag and NotificationPreferences
        assert "user_tags" in sql_query_str
        assert "notification_preferences" in sql_query_str

        # 2. Filtering active users
        assert "users.is_active" in sql_query_str

        # 3. Valid telegram_id (not null/empty)
        assert "users.telegram_id IS NOT NULL" in sql_query_str

        # 4. Creator ID excluded
        assert "users.id !=" in sql_query_str

        # 5. Preferences tag subscriptions is True
        assert "notification_preferences.tag_subscriptions" in sql_query_str

        # 6. Distinct and selectinload checks
        assert "DISTINCT" in sql_query_str
