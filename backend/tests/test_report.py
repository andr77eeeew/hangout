from datetime import datetime, timezone
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from httpx import AsyncClient
from pymongo.asynchronous.collection import AsyncCollection

from app.core.dependencies import get_current_user
from app.core.mongo import get_reports_collection
from app.main import app
from app.models.user import User, UserRole
from app.services.notification import NotificationService


@pytest.fixture
def mock_reports_col() -> AsyncMock:
    col = AsyncMock(spec=AsyncCollection)
    db = MagicMock()

    activities_col = AsyncMock()
    chat_messages_col = AsyncMock()

    # Mock __getitem__ so db["activities"] and db["chat_messages"] return async mocks
    db.__getitem__.side_effect = lambda name: {
        "activities": activities_col,
        "chat_messages": chat_messages_col,
    }[name]

    col.database = db
    return col


@pytest.fixture
def override_auth_and_mongo(mock_reports_col: AsyncMock, mock_user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_reports_collection] = lambda: mock_reports_col
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_reports_collection, None)


@pytest.mark.asyncio
async def test_create_report_success(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 1
    mock_user.user_role = UserRole.client

    reported_user = User(
        id=2,
        email="reported@user.com",
        username="reported",
        is_active=True,
        user_role=UserRole.client,
        created_at=datetime.now(timezone.utc),
    )

    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = reported_user
    mock_db.execute.return_value = db_result

    mock_reports_col.find_one.return_value = None

    insert_result = MagicMock()
    insert_result.inserted_id = ObjectId()
    mock_reports_col.insert_one.return_value = insert_result

    payload = {
        "reported_user_id": 2,
        "reason": "Harassment in chat",
        "activity_id": None,
        "chat_message_id": None,
    }

    response = await async_client.post("/reports", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["reporter_id"] == 1
    assert data["reported_user_id"] == 2
    assert data["reason"] == "Harassment in chat"
    assert data["status"] == "open"
    mock_reports_col.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_create_report_self_forbidden(
    async_client: AsyncClient,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 1

    payload = {
        "reported_user_id": 1,
        "reason": "Self report",
        "activity_id": None,
        "chat_message_id": None,
    }

    response = await async_client.post("/reports", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot report yourself"


@pytest.mark.asyncio
async def test_create_report_moderator_forbidden(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 1

    reported_moderator = User(
        id=2,
        email="mod@user.com",
        username="moderator",
        is_active=True,
        user_role=UserRole.moderator,
        created_at=datetime.now(timezone.utc),
    )

    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = reported_moderator
    mock_db.execute.return_value = db_result

    payload = {
        "reported_user_id": 2,
        "reason": "Reporting a mod",
        "activity_id": None,
        "chat_message_id": None,
    }

    response = await async_client.post("/reports", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot report a moderator/admin"


@pytest.mark.asyncio
async def test_create_report_user_not_found(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 1

    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = db_result

    payload = {
        "reported_user_id": 999,
        "reason": "Missing user",
        "activity_id": None,
        "chat_message_id": None,
    }

    response = await async_client.post("/reports", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.asyncio
async def test_create_report_activity_not_found(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 1

    reported_user = User(
        id=2,
        email="reported@user.com",
        username="reported",
        is_active=True,
        user_role=UserRole.client,
        created_at=datetime.now(timezone.utc),
    )

    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = reported_user
    mock_db.execute.return_value = db_result

    mock_reports_col.database["activities"].find_one.return_value = None

    payload = {
        "reported_user_id": 2,
        "reason": "Bad activity content",
        "activity_id": str(ObjectId()),
        "chat_message_id": None,
    }

    response = await async_client.post("/reports", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


@pytest.mark.asyncio
async def test_create_report_chat_message_not_found(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 1

    reported_user = User(
        id=2,
        email="reported@user.com",
        username="reported",
        is_active=True,
        user_role=UserRole.client,
        created_at=datetime.now(timezone.utc),
    )

    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = reported_user
    mock_db.execute.return_value = db_result

    mock_reports_col.database["activities"].find_one.return_value = {"_id": ObjectId()}
    mock_reports_col.database["chat_messages"].find_one.return_value = None

    payload = {
        "reported_user_id": 2,
        "reason": "Bad message",
        "activity_id": str(ObjectId()),
        "chat_message_id": str(ObjectId()),
    }

    response = await async_client.post("/reports", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Chat message not found"


@pytest.mark.asyncio
async def test_create_report_duplicate_conflict(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 1

    reported_user = User(
        id=2,
        email="reported@user.com",
        username="reported",
        is_active=True,
        user_role=UserRole.client,
        created_at=datetime.now(timezone.utc),
    )

    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = reported_user
    mock_db.execute.return_value = db_result

    mock_reports_col.database["activities"].find_one.return_value = {"_id": ObjectId()}

    mock_reports_col.find_one.return_value = {
        "_id": ObjectId(),
        "reporter_id": 1,
        "reported_user_id": 2,
        "status": "open",
    }

    payload = {
        "reported_user_id": 2,
        "reason": "Duplicate report",
        "activity_id": str(ObjectId()),
        "chat_message_id": None,
    }

    response = await async_client.post("/reports", json=payload)
    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "You have already reported this user in this context"
    )


@pytest.mark.asyncio
async def test_list_reports_as_moderator(
    async_client: AsyncClient,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.user_role = UserRole.moderator

    mock_reports_col.count_documents.return_value = 1

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": ObjectId(),
                "reporter_id": 1,
                "reported_user_id": 2,
                "activity_id": None,
                "chat_message_id": None,
                "reason": "spam",
                "status": "open",
                "moderator_id": None,
                "moderator_notes": None,
                "resolution": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "taken_at": None,
                "resolved_at": None,
            }
        ]
    )
    mock_reports_col.find.return_value = mock_cursor

    response = await async_client.get("/reports")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "open"


@pytest.mark.asyncio
async def test_list_reports_as_non_moderator_forbidden(
    async_client: AsyncClient,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.user_role = UserRole.client

    response = await async_client.get("/reports")
    assert response.status_code == 403
    assert response.json()["detail"] == "Permission denied"


@pytest.mark.asyncio
async def test_take_report_success(
    async_client: AsyncClient,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 5
    mock_user.user_role = UserRole.moderator

    report_id = ObjectId()
    mock_reports_col.find_one.return_value = {
        "_id": report_id,
        "reporter_id": 1,
        "reported_user_id": 2,
        "status": "open",
    }

    mock_reports_col.find_one_and_update.return_value = {
        "_id": report_id,
        "reporter_id": 1,
        "reported_user_id": 2,
        "status": "in_review",
        "moderator_id": 5,
        "reason": "Spam",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    response = await async_client.post(f"/reports/{report_id}/take")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_review"
    assert data["moderator_id"] == 5


@pytest.mark.asyncio
async def test_take_report_already_taken(
    async_client: AsyncClient,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.user_role = UserRole.moderator

    report_id = ObjectId()
    mock_reports_col.find_one.return_value = {
        "_id": report_id,
        "reporter_id": 1,
        "reported_user_id": 2,
        "status": "in_review",
        "moderator_id": 3,
    }

    response = await async_client.post(f"/reports/{report_id}/take")
    assert response.status_code == 400
    assert response.json()["detail"] == "Only open reports can be taken"


@pytest.mark.asyncio
async def test_resolve_report_success(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 5
    mock_user.user_role = UserRole.moderator

    report_id = ObjectId()
    mock_reports_col.find_one.return_value = {
        "_id": report_id,
        "reporter_id": 1,
        "reported_user_id": 2,
        "status": "in_review",
        "moderator_id": 5,
    }

    mock_reports_col.find_one_and_update.return_value = {
        "_id": report_id,
        "reporter_id": 1,
        "reported_user_id": 2,
        "status": "resolved",
        "moderator_id": 5,
        "resolution": "User warned",
        "reason": "Harassment",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with patch.object(NotificationService, "notify_report_update") as mock_notify:
        payload = {
            "resolution": "User warned",
            "moderator_notes": "First offense",
            "ban_user": False,
        }
        response = await async_client.post(
            f"/reports/{report_id}/resolve", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["resolution"] == "User warned"
        mock_notify.assert_called_once_with(
            user_id=1,
            report_id=str(report_id),
            status="resolved",
            resolution="User warned",
            db=mock_db,
        )


@pytest.mark.asyncio
async def test_resolve_report_with_ban(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 5
    mock_user.user_role = UserRole.moderator

    report_id = ObjectId()
    mock_reports_col.find_one.return_value = {
        "_id": report_id,
        "reporter_id": 1,
        "reported_user_id": 2,
        "status": "in_review",
        "moderator_id": 5,
    }

    mock_reports_col.find_one_and_update.return_value = {
        "_id": report_id,
        "reporter_id": 1,
        "reported_user_id": 2,
        "status": "resolved",
        "moderator_id": 5,
        "resolution": "User banned",
        "reason": "Cheating",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with (
        patch(
            "app.services.ban.BanService.ban_user", new_callable=AsyncMock
        ) as mock_ban,
        patch.object(NotificationService, "notify_report_update") as mock_notify,
    ):
        payload = {
            "resolution": "Severe violation",
            "moderator_notes": "Banned forever",
            "ban_user": True,
            "ban_reason": "Cheating and spamming",
        }
        response = await async_client.post(
            f"/reports/{report_id}/resolve", json=payload
        )
        assert response.status_code == 200
        mock_ban.assert_called_once_with(
            user_id=2,
            moderator=mock_user,
            reason="Cheating and spamming",
            db=mock_db,
            redis=ANY,
            report_id=str(report_id),
        )
        mock_notify.assert_called_once_with(
            user_id=1,
            report_id=str(report_id),
            status="resolved",
            resolution="Severe violation",
            db=mock_db,
        )


@pytest.mark.asyncio
async def test_resolve_report_assigned_moderator_only(
    async_client: AsyncClient,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 5
    mock_user.user_role = UserRole.moderator

    report_id = ObjectId()
    mock_reports_col.find_one.return_value = {
        "_id": report_id,
        "reporter_id": 1,
        "reported_user_id": 2,
        "status": "in_review",
        "moderator_id": 10,
    }

    payload = {
        "resolution": "Some resolution",
        "moderator_notes": "Notes",
        "ban_user": False,
    }
    response = await async_client.post(f"/reports/{report_id}/resolve", json=payload)
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Only the assigned moderator can resolve/dismiss this report"
    )


@pytest.mark.asyncio
async def test_dismiss_report_success(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.id = 5
    mock_user.user_role = UserRole.moderator

    report_id = ObjectId()
    mock_reports_col.find_one.return_value = {
        "_id": report_id,
        "reporter_id": 1,
        "reported_user_id": 2,
        "status": "in_review",
        "moderator_id": 5,
    }

    mock_reports_col.find_one_and_update.return_value = {
        "_id": report_id,
        "reporter_id": 1,
        "reported_user_id": 2,
        "status": "dismissed",
        "moderator_id": 5,
        "resolution": "False alarm",
        "reason": "Harassment",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with patch.object(NotificationService, "notify_report_update") as mock_notify:
        payload = {
            "resolution": "False alarm",
            "moderator_notes": "No policy violation",
        }
        response = await async_client.post(
            f"/reports/{report_id}/dismiss", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "dismissed"
        assert data["resolution"] == "False alarm"
        mock_notify.assert_called_once_with(
            user_id=1,
            report_id=str(report_id),
            status="dismissed",
            resolution="False alarm",
            db=mock_db,
        )


@pytest.mark.asyncio
async def test_get_user_reports_as_moderator(
    async_client: AsyncClient,
    mock_db: AsyncMock,
    mock_reports_col: AsyncMock,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.user_role = UserRole.moderator

    target_user = User(
        id=10,
        is_active=True,
        username="badguy",
        created_at=datetime.now(timezone.utc),
    )
    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = target_user
    mock_db.execute.return_value = db_result

    mock_reports_col.count_documents.return_value = 1

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": ObjectId(),
                "reporter_id": 1,
                "reported_user_id": 10,
                "activity_id": None,
                "chat_message_id": None,
                "reason": "Cheating",
                "status": "resolved",
                "moderator_id": 5,
                "moderator_notes": None,
                "resolution": "Banned",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "taken_at": None,
                "resolved_at": None,
            }
        ]
    )
    mock_reports_col.find.return_value = mock_cursor

    response = await async_client.get("/reports/user/10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_get_user_reports_as_user_forbidden(
    async_client: AsyncClient,
    mock_user: User,
    override_auth_and_mongo: None,
) -> None:
    mock_user.user_role = UserRole.client

    response = await async_client.get("/reports/user/10")
    assert response.status_code == 403
    assert response.json()["detail"] == "Permission denied"
