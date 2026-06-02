from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
import pytest
from httpx import AsyncClient
from app.models.user import User, UserRole
from app.main import app
from app.core.mongo import get_reports_collection

# Default headers
HEADERS_VALID = {"X-Internal-Key": "test_internal_key"}
HEADERS_INVALID = {"X-Internal-Key": "invalid_key"}


def setup_acting_user(mock_db: AsyncMock, user: User) -> None:
    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = db_result


@pytest.fixture
def mock_reports_col() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def override_reports_mongo(mock_reports_col: AsyncMock) -> None:
    app.dependency_overrides[get_reports_collection] = lambda: mock_reports_col
    yield
    app.dependency_overrides.pop(get_reports_collection, None)


def get_mock_activity_doc(user_id: int) -> dict:
    return {
        "_id": ObjectId(),
        "creator_id": user_id,
        "title": "Internal test activity",
        "type": "open",
        "format": "online",
        "category": "games",
        "extra_data": {
            "category": "games",
            "game_name": "Minecraft",
            "platform": "pc",
        },
        "description": "This is a long enough test description for activity.",
        "date": datetime.now(timezone.utc) + timedelta(days=1),
        "max_members": 5,
        "tags": ["gaming"],
        "location": None,
        "current_members": 1,
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


# --- General Auth Verification Tests ---


@pytest.mark.asyncio
async def test_internal_endpoints_auth_failures(async_client: AsyncClient) -> None:
    endpoints = [
        ("GET", "/internal/users/1/activities"),
        ("GET", "/internal/users/1/memberships"),
        ("GET", "/internal/activities/507f1f77bcf86cd799439011"),
        ("POST", "/internal/users/1/activities"),
        ("POST", "/internal/users/1/activities/507f1f77bcf86cd799439011/join"),
        (
            "GET",
            "/internal/users/1/activities/507f1f77bcf86cd799439011/pending-members",
        ),
        ("POST", "/internal/users/1/memberships/507f1f77bcf86cd799439011/approve"),
        ("POST", "/internal/users/1/memberships/507f1f77bcf86cd799439011/reject"),
        ("POST", "/internal/users/1/memberships/507f1f77bcf86cd799439011/kick"),
        ("GET", "/internal/users/1/tags/favorites"),
        ("POST", "/internal/users/1/tags/gaming/favorite"),
        ("DELETE", "/internal/users/1/tags/gaming/favorite"),
        ("GET", "/internal/moderation/reports"),
        ("POST", "/internal/moderation/reports/507f1f77bcf86cd799439011/take"),
        ("POST", "/internal/moderation/reports/507f1f77bcf86cd799439011/resolve"),
        ("POST", "/internal/moderation/reports/507f1f77bcf86cd799439011/dismiss"),
        ("POST", "/internal/moderation/users/1/ban"),
        ("POST", "/internal/moderation/users/1/unban"),
        ("GET", "/internal/moderation/reports/507f1f77bcf86cd799439011"),
    ]

    for method, path in endpoints:
        # 1. Missing header
        res = await async_client.request(method, path)
        assert res.status_code == 403, (
            f"{method} {path} missing header expected 403, got {res.status_code}"
        )
        assert res.json()["detail"] == "Invalid internal API key"

        # 2. Invalid header
        res2 = await async_client.request(method, path, headers=HEADERS_INVALID)
        assert res2.status_code == 403, (
            f"{method} {path} invalid header expected 403, got {res2.status_code}"
        )
        assert res2.json()["detail"] == "Invalid internal API key"


# --- Activity Endpoint Tests ---


@pytest.mark.asyncio
async def test_get_user_created_activities(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_mongo: AsyncMock,
    mock_user: User,
) -> None:
    mock_user.id = 1
    setup_acting_user(mock_db, mock_user)

    mock_doc = get_mock_activity_doc(1)

    cursor = MagicMock()
    sorted_cursor = MagicMock()
    sorted_cursor.to_list = AsyncMock(return_value=[mock_doc])
    cursor.sort.return_value = sorted_cursor
    mock_mongo.find = MagicMock(return_value=cursor)

    res = await async_client.get("/internal/users/1/activities", headers=HEADERS_VALID)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["title"] == "Internal test activity"
    mock_mongo.find.assert_called_once_with({"creator_id": 1})


@pytest.mark.asyncio
async def test_get_user_joined_activities(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_mongo: AsyncMock,
    mock_membership_col: AsyncMock,
    mock_user: User,
) -> None:
    mock_user.id = 1
    setup_acting_user(mock_db, mock_user)

    act_id = ObjectId()

    membership_cursor = MagicMock()
    membership_cursor.to_list = AsyncMock(
        return_value=[{"activity_id": act_id, "user_id": 1, "status": "approved"}]
    )
    mock_membership_col.find = MagicMock(return_value=membership_cursor)

    mock_doc = get_mock_activity_doc(2)
    mock_doc["_id"] = act_id

    cursor = MagicMock()
    sorted_cursor = MagicMock()
    sorted_cursor.to_list = AsyncMock(return_value=[mock_doc])
    cursor.sort.return_value = sorted_cursor
    mock_mongo.find = MagicMock(return_value=cursor)

    res = await async_client.get("/internal/users/1/memberships", headers=HEADERS_VALID)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["title"] == "Internal test activity"
    mock_membership_col.find.assert_called_once_with(
        {"user_id": 1, "status": "approved"}
    )
    mock_mongo.find.assert_called_once_with({"_id": {"$in": [act_id]}})


@pytest.mark.asyncio
async def test_get_internal_activity(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_mongo: AsyncMock,
    mock_user: User,
) -> None:
    act_id = ObjectId()
    mock_doc = get_mock_activity_doc(1)
    mock_doc["_id"] = act_id
    mock_mongo.find_one.return_value = mock_doc

    setup_acting_user(mock_db, mock_user)

    res = await async_client.get(
        f"/internal/activities/{act_id}", headers=HEADERS_VALID
    )
    assert res.status_code == 200
    assert res.json()["title"] == "Internal test activity"
    mock_mongo.find_one.assert_called_once_with({"_id": act_id})


@pytest.mark.asyncio
async def test_create_activity_on_behalf(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_mongo: AsyncMock,
    mock_membership_col: MagicMock,
    mock_user: User,
) -> None:
    mock_user.id = 1
    setup_acting_user(mock_db, mock_user)

    act_id = ObjectId()
    insert_result = MagicMock()
    insert_result.inserted_id = act_id
    mock_mongo.insert_one.return_value = insert_result

    # Mock return value for created activity query (find_one)
    mock_doc = get_mock_activity_doc(1)
    mock_doc["_id"] = act_id
    mock_mongo.find_one.return_value = mock_doc

    payload = {
        "title": "Brand new activity",
        "type": "open",
        "format": "online",
        "category": "games",
        "extra_data": {
            "category": "games",
            "game_name": "Counter-Strike",
            "platform": "pc",
        },
        "description": "We need players for matchmaking session tonight.",
        "date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "max_members": 5,
        "tags": ["gaming", "cs"],
        "location": None,
    }

    res = await async_client.post(
        "/internal/users/1/activities", json=payload, headers=HEADERS_VALID
    )
    assert res.status_code == 201
    assert res.json()["title"] == "Internal test activity"
    mock_mongo.insert_one.assert_called_once()
    mock_membership_col.insert_one.assert_called_once()


# --- Membership Endpoint Tests ---


@pytest.mark.asyncio
async def test_join_activity_on_behalf(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_mongo: AsyncMock,
    mock_membership_col: AsyncMock,
    mock_user: User,
) -> None:
    mock_user.id = 1
    setup_acting_user(mock_db, mock_user)

    act_id = ObjectId()
    mock_doc = get_mock_activity_doc(2)  # creator_id = 2
    mock_doc["_id"] = act_id
    mock_doc["max_members"] = 10
    mock_doc["current_members"] = 2
    mock_doc["type"] = "open"
    mock_mongo.find_one.return_value = mock_doc

    memb_id = ObjectId()
    mock_membership_col.find_one.return_value = {
        "_id": memb_id,
        "activity_id": act_id,
        "user_id": 1,
        "status": "approved",
        "joined_at": datetime.now(timezone.utc),
    }

    insert_result = MagicMock()
    insert_result.inserted_id = memb_id
    mock_membership_col.insert_one.return_value = insert_result

    # Mock incrementing members count
    mock_mongo.find_one_and_update.return_value = mock_doc

    res = await async_client.post(
        f"/internal/users/1/activities/{act_id}/join", headers=HEADERS_VALID
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "approved"
    mock_membership_col.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_get_pending_members_on_behalf(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_mongo: AsyncMock,
    mock_membership_col: AsyncMock,
    mock_user: User,
) -> None:
    mock_user.id = 1
    setup_acting_user(mock_db, mock_user)

    act_id = ObjectId()
    mock_doc = get_mock_activity_doc(1)  # creator_id = 1
    mock_doc["_id"] = act_id
    mock_mongo.find_one.return_value = mock_doc

    memb_id = ObjectId()

    pending_cursor = MagicMock()
    pending_cursor.to_list = AsyncMock(
        return_value=[
            {
                "_id": memb_id,
                "activity_id": act_id,
                "user_id": 2,
                "status": "pending",
                "joined_at": datetime.now(timezone.utc),
            }
        ]
    )
    mock_membership_col.find = MagicMock(return_value=pending_cursor)

    other_user = User(
        id=2,
        username="otheruser",
        is_active=True,
        user_role=UserRole.client,
        created_at=datetime.now(timezone.utc),
    )
    db_result = MagicMock()
    # Mocking first query for acting user then second query for the other user
    db_result.scalar_one_or_none.return_value = mock_user
    db_result.scalars.return_value.all.return_value = [other_user]
    mock_db.execute.side_effect = [db_result, db_result]

    res = await async_client.get(
        f"/internal/users/1/activities/{act_id}/pending-members", headers=HEADERS_VALID
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["user_id"] == 2
    assert data["items"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_approve_membership_on_behalf(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_mongo: AsyncMock,
    mock_membership_col: AsyncMock,
    mock_user: User,
) -> None:
    mock_user.id = 1
    setup_acting_user(mock_db, mock_user)

    act_id = ObjectId()
    memb_id = ObjectId()

    mock_membership_col.find_one.return_value = {
        "_id": memb_id,
        "activity_id": act_id,
        "user_id": 2,
        "status": "pending",
        "joined_at": datetime.now(timezone.utc),
    }

    mock_doc = get_mock_activity_doc(1)  # creator is 1
    mock_doc["_id"] = act_id
    mock_mongo.find_one.return_value = mock_doc

    mock_membership_col.find_one_and_update.return_value = {
        "_id": memb_id,
        "activity_id": act_id,
        "user_id": 2,
        "status": "approved",
        "joined_at": datetime.now(timezone.utc),
    }

    mock_mongo.update_one = AsyncMock()

    # Patched to avoid actual background notifications trying to send
    with patch(
        "app.services.notification.NotificationService.notify_membership_change",
        new_callable=AsyncMock,
    ):
        res = await async_client.post(
            f"/internal/users/1/memberships/{memb_id}/approve", headers=HEADERS_VALID
        )
        assert res.status_code == 200
        assert res.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_membership_on_behalf(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_mongo: AsyncMock,
    mock_membership_col: AsyncMock,
    mock_user: User,
) -> None:
    mock_user.id = 1
    setup_acting_user(mock_db, mock_user)

    act_id = ObjectId()
    memb_id = ObjectId()

    mock_membership_col.find_one.return_value = {
        "_id": memb_id,
        "activity_id": act_id,
        "user_id": 2,
        "status": "pending",
        "joined_at": datetime.now(timezone.utc),
    }

    mock_doc = get_mock_activity_doc(1)
    mock_doc["_id"] = act_id
    mock_mongo.find_one.return_value = mock_doc

    mock_membership_col.find_one_and_update.return_value = {
        "_id": memb_id,
        "activity_id": act_id,
        "user_id": 2,
        "status": "rejected",
        "joined_at": datetime.now(timezone.utc),
    }

    with patch(
        "app.services.notification.NotificationService.notify_membership_change",
        new_callable=AsyncMock,
    ):
        res = await async_client.post(
            f"/internal/users/1/memberships/{memb_id}/reject", headers=HEADERS_VALID
        )
        assert res.status_code == 200
        assert res.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_kick_membership_on_behalf(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_mongo: AsyncMock,
    mock_membership_col: AsyncMock,
    mock_user: User,
) -> None:
    mock_user.id = 1
    setup_acting_user(mock_db, mock_user)

    act_id = ObjectId()
    memb_id = ObjectId()

    mock_membership_col.find_one.return_value = {
        "_id": memb_id,
        "activity_id": act_id,
        "user_id": 2,
        "status": "approved",
        "joined_at": datetime.now(timezone.utc),
    }

    mock_doc = get_mock_activity_doc(1)
    mock_doc["_id"] = act_id
    mock_mongo.find_one.return_value = mock_doc

    mock_membership_col.find_one_and_update.return_value = {
        "_id": memb_id,
        "activity_id": act_id,
        "user_id": 2,
        "status": "kicked",
        "joined_at": datetime.now(timezone.utc),
    }

    mock_mongo.update_one = AsyncMock()

    with patch(
        "app.services.notification.NotificationService.notify_membership_change",
        new_callable=AsyncMock,
    ):
        res = await async_client.post(
            f"/internal/users/1/memberships/{memb_id}/kick", headers=HEADERS_VALID
        )
        assert res.status_code == 200
        assert res.json()["status"] == "kicked"


# --- Tag Endpoint Tests ---


@pytest.mark.asyncio
async def test_get_user_favorite_tags(
    async_client: AsyncClient, mock_db: AsyncMock, mock_user: User
) -> None:
    mock_user.id = 1
    tag_mock = MagicMock()
    tag_mock.id = 10
    tag_mock.name = "gaming"
    tag_mock.slug = "gaming"
    mock_user.favorite_tags = [tag_mock]
    setup_acting_user(mock_db, mock_user)

    res = await async_client.get(
        "/internal/users/1/tags/favorites", headers=HEADERS_VALID
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "gaming"


@pytest.mark.asyncio
async def test_add_favorite_tag(
    async_client: AsyncClient, mock_db: AsyncMock, mock_user: User
) -> None:
    mock_user.id = 1
    setup_acting_user(mock_db, mock_user)

    with patch(
        "app.services.tag.TagService.add_favorite_tag", new_callable=AsyncMock
    ) as add_mock:
        add_mock.return_value = {
            "status": "success",
            "tag": {"id": 1, "name": "gaming", "slug": "gaming"},
        }
        res = await async_client.post(
            "/internal/users/1/tags/gaming/favorite", headers=HEADERS_VALID
        )
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        add_mock.assert_called_once_with(
            tag_name="gaming", db=mock_db, current_user=mock_user
        )


@pytest.mark.asyncio
async def test_remove_favorite_tag(
    async_client: AsyncClient, mock_db: AsyncMock, mock_user: User
) -> None:
    mock_user.id = 1
    setup_acting_user(mock_db, mock_user)

    with patch(
        "app.services.tag.TagService.remove_favorite_tag", new_callable=AsyncMock
    ) as rm_mock:
        rm_mock.return_value = {
            "status": "success",
            "tag": {"id": 1, "name": "gaming", "slug": "gaming"},
        }
        res = await async_client.delete(
            "/internal/users/1/tags/gaming/favorite", headers=HEADERS_VALID
        )
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        rm_mock.assert_called_once_with(
            tag_name="gaming", db=mock_db, current_user=mock_user
        )


# --- Moderation Endpoint Tests ---


@pytest.mark.asyncio
async def test_list_reports_internal(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_reports_mongo: None,
) -> None:
    mock_user.id = 1
    mock_user.user_role = UserRole.moderator
    setup_acting_user(mock_db, mock_user)

    report_doc = {
        "_id": ObjectId(),
        "reporter_id": 2,
        "reported_user_id": 3,
        "reason": "bad behavior",
        "status": "open",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    mock_reports_col.count_documents = AsyncMock(return_value=1)

    cursor = MagicMock()
    sorted_cursor = MagicMock()
    limited_cursor = MagicMock()
    limited_cursor.to_list = AsyncMock(return_value=[report_doc])
    sorted_cursor.limit.return_value = limited_cursor
    cursor.sort.return_value = sorted_cursor
    mock_reports_col.find = MagicMock(return_value=cursor)

    res = await async_client.get(
        "/internal/moderation/reports?moderator_id=1&status=open", headers=HEADERS_VALID
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["reason"] == "bad behavior"


@pytest.mark.asyncio
async def test_take_report_internal(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_reports_mongo: None,
) -> None:
    mock_user.id = 1
    mock_user.user_role = UserRole.moderator
    setup_acting_user(mock_db, mock_user)

    rep_id = ObjectId()
    report_doc = {
        "_id": rep_id,
        "reporter_id": 2,
        "reported_user_id": 3,
        "reason": "bad behavior",
        "status": "open",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    mock_reports_col.find_one.return_value = report_doc
    mock_reports_col.find_one_and_update.return_value = {
        **report_doc,
        "status": "in_review",
        "moderator_id": 1,
        "taken_at": datetime.now(timezone.utc),
    }

    res = await async_client.post(
        f"/internal/moderation/reports/{rep_id}/take?moderator_id=1",
        headers=HEADERS_VALID,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "in_review"
    assert res.json()["moderator_id"] == 1


@pytest.mark.asyncio
async def test_resolve_report_internal(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_redis: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_reports_mongo: None,
) -> None:
    mock_user.id = 1
    mock_user.user_role = UserRole.moderator
    setup_acting_user(mock_db, mock_user)

    rep_id = ObjectId()
    report_doc = {
        "_id": rep_id,
        "reporter_id": 2,
        "reported_user_id": 3,
        "reason": "bad behavior",
        "status": "in_review",
        "moderator_id": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "taken_at": datetime.now(timezone.utc),
    }

    mock_reports_col.find_one.return_value = report_doc
    mock_reports_col.find_one_and_update.return_value = {
        **report_doc,
        "status": "resolved",
        "resolution": "user warned",
        "resolved_at": datetime.now(timezone.utc),
    }

    payload = {
        "resolution": "user warned",
        "moderator_notes": "notes",
        "ban_user": False,
    }

    res = await async_client.post(
        f"/internal/moderation/reports/{rep_id}/resolve?moderator_id=1",
        json=payload,
        headers=HEADERS_VALID,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_dismiss_report_internal(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_reports_mongo: None,
) -> None:
    mock_user.id = 1
    mock_user.user_role = UserRole.moderator
    setup_acting_user(mock_db, mock_user)

    rep_id = ObjectId()
    report_doc = {
        "_id": rep_id,
        "reporter_id": 2,
        "reported_user_id": 3,
        "reason": "bad behavior",
        "status": "in_review",
        "moderator_id": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "taken_at": datetime.now(timezone.utc),
    }

    mock_reports_col.find_one.return_value = report_doc
    mock_reports_col.find_one_and_update.return_value = {
        **report_doc,
        "status": "dismissed",
        "resolution": "no violation",
        "resolved_at": datetime.now(timezone.utc),
    }

    payload = {
        "resolution": "no violation",
        "moderator_notes": "notes",
    }

    res = await async_client.post(
        f"/internal/moderation/reports/{rep_id}/dismiss?moderator_id=1",
        json=payload,
        headers=HEADERS_VALID,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "dismissed"


@pytest.mark.asyncio
async def test_ban_user_internal(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_redis: AsyncMock,
    mock_user: User,
) -> None:
    mock_user.id = 1
    mock_user.user_role = UserRole.moderator
    mock_user.created_at = datetime.now(timezone.utc)

    reported_user = User(
        id=2,
        username="reported",
        email="rep@user.com",
        is_active=True,
        is_banned=False,
        created_at=datetime.now(timezone.utc),
    )

    db_result = MagicMock()
    # Mocking first query for acting user, then second for the banned user
    db_result.scalar_one_or_none.side_effect = [mock_user, reported_user]
    mock_db.execute.return_value = db_result

    payload = {
        "reason": "Spamming",
    }

    res = await async_client.post(
        "/internal/moderation/users/2/ban?moderator_id=1",
        json=payload,
        headers=HEADERS_VALID,
    )
    assert res.status_code == 200
    assert res.json()["is_banned"] is True


@pytest.mark.asyncio
async def test_unban_user_internal(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_user: User,
) -> None:
    mock_user.id = 1
    mock_user.user_role = UserRole.moderator
    mock_user.created_at = datetime.now(timezone.utc)

    reported_user = User(
        id=2,
        username="reported",
        email="rep@user.com",
        is_active=True,
        is_banned=True,
        created_at=datetime.now(timezone.utc),
    )

    db_result = MagicMock()
    db_result.scalar_one_or_none.side_effect = [mock_user, reported_user]
    mock_db.execute.return_value = db_result

    payload = {
        "reason": "Ban expired",
    }

    res = await async_client.post(
        "/internal/moderation/users/2/unban?moderator_id=1",
        json=payload,
        headers=HEADERS_VALID,
    )
    assert res.status_code == 200
    assert res.json()["is_banned"] is False


@pytest.mark.asyncio
async def test_get_report_internal(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_reports_mongo: None,
) -> None:
    mock_user.id = 1
    mock_user.user_role = UserRole.moderator
    setup_acting_user(mock_db, mock_user)

    rep_id = ObjectId()
    report_doc = {
        "_id": rep_id,
        "reporter_id": 2,
        "reported_user_id": 3,
        "reason": "bad behavior",
        "status": "open",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    mock_reports_col.find_one.return_value = report_doc

    res = await async_client.get(
        f"/internal/moderation/reports/{rep_id}?moderator_id=1", headers=HEADERS_VALID
    )
    assert res.status_code == 200
    assert res.json()["reason"] == "bad behavior"
    mock_reports_col.find_one.assert_called_once_with({"_id": rep_id})
