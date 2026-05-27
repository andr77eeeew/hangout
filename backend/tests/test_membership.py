from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.dependencies import get_current_user
from app.main import app
from app.models.user import User, UserRole

VALID_OID = str(ObjectId())
VALID_MEMBERSHIP_OID = str(ObjectId())


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_activity(
    *,
    creator_id: int = 99,
    status: str = "active",
    activity_type: str = "open",
    max_members: int = 10,
    current_members: int = 1,
):
    return {
        "_id": ObjectId(VALID_OID),
        "creator_id": creator_id,
        "status": status,
        "type": activity_type,
        "max_members": max_members,
        "current_members": current_members,
    }


def _make_membership(
    *,
    membership_id: str | None = None,
    activity_id: str | None = None,
    user_id: int = 2,
    membership_status: str = "approved",
):
    return {
        "_id": ObjectId(membership_id or VALID_MEMBERSHIP_OID),
        "activity_id": ObjectId(activity_id or VALID_OID),
        "user_id": user_id,
        "status": membership_status,
        "joined_at": datetime.now(timezone.utc),
    }


def _make_user(user_id: int = 1, role: UserRole = UserRole.client):
    return User(
        id=user_id,
        email=f"user{user_id}@test.com",
        username=f"user{user_id}",
        is_active=True,
        password="hashed",
        avatar="avatars/test.jpg",
        banner=None,
        created_at=datetime.now(timezone.utc),
        user_role=role,
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def override_auth(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ═════════════════════════════════════════════════════════════════════════════
# JOIN ACTIVITY
# ═════════════════════════════════════════════════════════════════════════════


class TestJoinActivity:
    """POST /activities/{activity_id}/join"""

    async def test_join_open_activity_success(
        self, async_client, mock_mongo, mock_membership_col
    ):
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=99))
        inserted_id = ObjectId()
        mock_membership_col.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=inserted_id)
        )
        mock_mongo.find_one_and_update = AsyncMock(
            return_value=_make_activity(current_members=2)
        )
        mock_membership_col.find_one = AsyncMock(
            return_value=_make_membership(membership_id=str(inserted_id), user_id=1)
        )

        response = await async_client.post(f"/activities/{VALID_OID}/join")

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "approved"
        assert data["user_id"] == 1

    async def test_join_closed_activity_pending(
        self, async_client, mock_mongo, mock_membership_col
    ):
        mock_mongo.find_one = AsyncMock(
            return_value=_make_activity(creator_id=99, activity_type="closed")
        )
        inserted_id = ObjectId()
        mock_membership_col.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=inserted_id)
        )
        mock_membership_col.find_one = AsyncMock(
            return_value=_make_membership(
                membership_id=str(inserted_id),
                user_id=1,
                membership_status="pending",
            )
        )

        response = await async_client.post(f"/activities/{VALID_OID}/join")

        assert response.status_code == 201
        assert response.json()["status"] == "pending"
        # current_members should not increment for pending
        mock_mongo.find_one_and_update.assert_not_called()

    async def test_join_own_activity_fails(
        self, async_client, mock_mongo, mock_membership_col
    ):
        # creator_id == mock_user.id (1)
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=1))

        response = await async_client.post(f"/activities/{VALID_OID}/join")

        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot join own activity"

    async def test_join_already_member_fails(
        self, async_client, mock_mongo, mock_membership_col
    ):
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=99))
        mock_membership_col.insert_one = AsyncMock(
            side_effect=DuplicateKeyError("duplicate")
        )

        response = await async_client.post(f"/activities/{VALID_OID}/join")

        assert response.status_code == 409
        assert response.json()["detail"] == "Already applied to this activity"

    async def test_join_full_activity_fails(
        self, async_client, mock_mongo, mock_membership_col
    ):
        mock_mongo.find_one = AsyncMock(
            return_value=_make_activity(
                creator_id=99, current_members=10, max_members=10
            )
        )

        response = await async_client.post(f"/activities/{VALID_OID}/join")

        assert response.status_code == 400
        assert response.json()["detail"] == "Activity is full"

    async def test_join_inactive_activity_fails(
        self, async_client, mock_mongo, mock_membership_col
    ):
        mock_mongo.find_one = AsyncMock(
            return_value=_make_activity(creator_id=99, status="canceled")
        )

        response = await async_client.post(f"/activities/{VALID_OID}/join")

        assert response.status_code == 400
        assert response.json()["detail"] == "Activity is not active"

    async def test_join_invalid_activity_id(self, async_client):
        response = await async_client.post("/activities/not-an-oid/join")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid activity id"

    async def test_join_activity_not_found(
        self, async_client, mock_mongo, mock_membership_col
    ):
        mock_mongo.find_one = AsyncMock(return_value=None)

        response = await async_client.post(f"/activities/{VALID_OID}/join")

        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"

    async def test_join_race_condition_full(
        self, async_client, mock_mongo, mock_membership_col
    ):
        """Atomic $inc returns None → activity filled between check and update."""
        mock_mongo.find_one = AsyncMock(
            return_value=_make_activity(
                creator_id=99, current_members=9, max_members=10
            )
        )
        inserted_id = ObjectId()
        mock_membership_col.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=inserted_id)
        )
        # Atomic update fails — activity full (race condition)
        mock_mongo.find_one_and_update = AsyncMock(return_value=None)
        mock_membership_col.delete_one = AsyncMock()

        response = await async_client.post(f"/activities/{VALID_OID}/join")

        assert response.status_code == 400
        assert response.json()["detail"] == "Activity is full"
        # Membership должен быть откатан
        mock_membership_col.delete_one.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════════
# APPROVE MEMBER
# ═════════════════════════════════════════════════════════════════════════════


class TestApproveMember:
    """POST /activities/{activity_id}/members/{membership_id}/approve"""

    async def test_approve_member_success(
        self, async_client, mock_mongo, mock_membership_col
    ):
        membership = _make_membership(membership_status="pending", user_id=2)
        mock_membership_col.find_one = AsyncMock(return_value=membership)
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=1))
        mock_mongo.find_one_and_update = AsyncMock(
            return_value=_make_activity(current_members=2)
        )
        mock_membership_col.find_one_and_update = AsyncMock(
            return_value={**membership, "status": "approved"}
        )

        response = await async_client.post(
            f"/activities/{VALID_OID}/members/{VALID_MEMBERSHIP_OID}/approve"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    async def test_approve_non_creator_fails(
        self, async_client, mock_mongo, mock_membership_col
    ):
        membership = _make_membership(membership_status="pending", user_id=2)
        mock_membership_col.find_one = AsyncMock(return_value=membership)
        # creator_id != current_user.id (1), and user is not a moderator
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=99))

        response = await async_client.post(
            f"/activities/{VALID_OID}/members/{VALID_MEMBERSHIP_OID}/approve"
        )

        assert response.status_code == 403

    async def test_approve_non_pending_fails(
        self, async_client, mock_mongo, mock_membership_col
    ):
        # Membership already approved - cannot approve again
        membership = _make_membership(membership_status="approved", user_id=2)
        mock_membership_col.find_one = AsyncMock(return_value=membership)
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=1))

        response = await async_client.post(
            f"/activities/{VALID_OID}/members/{VALID_MEMBERSHIP_OID}/approve"
        )

        assert response.status_code == 400
        assert "pending" in response.json()["detail"].lower()

    async def test_approve_when_full_fails(
        self, async_client, mock_mongo, mock_membership_col
    ):
        membership = _make_membership(membership_status="pending", user_id=2)
        mock_membership_col.find_one = AsyncMock(return_value=membership)
        mock_mongo.find_one = AsyncMock(
            return_value=_make_activity(
                creator_id=1, current_members=10, max_members=10
            )
        )
        # Atomic $inc returns None → full
        mock_mongo.find_one_and_update = AsyncMock(return_value=None)

        response = await async_client.post(
            f"/activities/{VALID_OID}/members/{VALID_MEMBERSHIP_OID}/approve"
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Activity is full"

    async def test_approve_as_moderator_success(
        self, async_client, mock_mongo, mock_membership_col
    ):
        """Moderator can approve a member of someone else's activity."""
        mod_user = _make_user(user_id=1, role=UserRole.moderator)
        app.dependency_overrides[get_current_user] = lambda: mod_user

        membership = _make_membership(membership_status="pending", user_id=2)
        mock_membership_col.find_one = AsyncMock(return_value=membership)
        # creator_id != moderator.id, but moderator has permission
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=99))
        mock_mongo.find_one_and_update = AsyncMock(
            return_value=_make_activity(current_members=2)
        )
        mock_membership_col.find_one_and_update = AsyncMock(
            return_value={**membership, "status": "approved"}
        )

        response = await async_client.post(
            f"/activities/{VALID_OID}/members/{VALID_MEMBERSHIP_OID}/approve"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "approved"


# ═════════════════════════════════════════════════════════════════════════════
# REJECT MEMBER
# ═════════════════════════════════════════════════════════════════════════════


class TestRejectMember:
    """POST /activities/{activity_id}/members/{membership_id}/reject"""

    async def test_reject_member_success(
        self, async_client, mock_mongo, mock_membership_col
    ):
        membership = _make_membership(membership_status="pending", user_id=2)
        mock_membership_col.find_one = AsyncMock(return_value=membership)
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=1))
        mock_membership_col.find_one_and_update = AsyncMock(
            return_value={**membership, "status": "rejected"}
        )

        response = await async_client.post(
            f"/activities/{VALID_OID}/members/{VALID_MEMBERSHIP_OID}/reject"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

    async def test_reject_non_pending_fails(
        self, async_client, mock_mongo, mock_membership_col
    ):
        membership = _make_membership(membership_status="approved", user_id=2)
        mock_membership_col.find_one = AsyncMock(return_value=membership)
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=1))

        response = await async_client.post(
            f"/activities/{VALID_OID}/members/{VALID_MEMBERSHIP_OID}/reject"
        )

        assert response.status_code == 400
        assert "pending" in response.json()["detail"].lower()


# ═════════════════════════════════════════════════════════════════════════════
# KICK MEMBER
# ═════════════════════════════════════════════════════════════════════════════


class TestKickMember:
    """POST /activities/{activity_id}/members/{membership_id}/kick"""

    async def test_kick_member_success(
        self, async_client, mock_mongo, mock_membership_col
    ):
        membership = _make_membership(membership_status="approved", user_id=2)
        mock_membership_col.find_one = AsyncMock(return_value=membership)
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=1))
        mock_membership_col.find_one_and_update = AsyncMock(
            return_value={**membership, "status": "kicked"}
        )
        mock_mongo.find_one_and_update = AsyncMock(
            return_value=_make_activity(current_members=1)
        )

        response = await async_client.post(
            f"/activities/{VALID_OID}/members/{VALID_MEMBERSHIP_OID}/kick"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "kicked"
        # current_members should be decremented
        mock_mongo.find_one_and_update.assert_called_once()

    async def test_kick_non_approved_fails(
        self, async_client, mock_mongo, mock_membership_col
    ):
        membership = _make_membership(membership_status="pending", user_id=2)
        mock_membership_col.find_one = AsyncMock(return_value=membership)
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=1))

        response = await async_client.post(
            f"/activities/{VALID_OID}/members/{VALID_MEMBERSHIP_OID}/kick"
        )

        assert response.status_code == 400
        assert "approved" in response.json()["detail"].lower()

    async def test_kick_self_fails(self, async_client, mock_mongo, mock_membership_col):
        """Creator cannot kick themselves."""
        # membership.user_id == current_user.id (1)
        membership = _make_membership(membership_status="approved", user_id=1)
        mock_membership_col.find_one = AsyncMock(return_value=membership)
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=1))

        response = await async_client.post(
            f"/activities/{VALID_OID}/members/{VALID_MEMBERSHIP_OID}/kick"
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot kick yourself"

    async def test_kick_non_creator_fails(
        self, async_client, mock_mongo, mock_membership_col
    ):
        membership = _make_membership(membership_status="approved", user_id=2)
        mock_membership_col.find_one = AsyncMock(return_value=membership)
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=99))

        response = await async_client.post(
            f"/activities/{VALID_OID}/members/{VALID_MEMBERSHIP_OID}/kick"
        )

        assert response.status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# LEAVE ACTIVITY
# ═════════════════════════════════════════════════════════════════════════════


class TestLeaveActivity:
    """POST /activities/{activity_id}/leave"""

    async def test_leave_activity_success(
        self, async_client, mock_mongo, mock_membership_col
    ):
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=99))
        mock_membership_col.find_one = AsyncMock(
            return_value=_make_membership(user_id=1, membership_status="approved")
        )
        mock_membership_col.update_one = AsyncMock()
        mock_mongo.find_one_and_update = AsyncMock(
            return_value=_make_activity(current_members=1)
        )

        response = await async_client.post(f"/activities/{VALID_OID}/leave")

        assert response.status_code == 204
        mock_membership_col.update_one.assert_called_once()
        mock_mongo.find_one_and_update.assert_called_once()

    async def test_creator_cannot_leave(
        self, async_client, mock_mongo, mock_membership_col
    ):
        # creator_id == current_user.id (1)
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=1))

        response = await async_client.post(f"/activities/{VALID_OID}/leave")

        assert response.status_code == 400
        assert response.json()["detail"] == "Creator cannot leave own activity"

    async def test_leave_no_membership(
        self, async_client, mock_mongo, mock_membership_col
    ):
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=99))
        mock_membership_col.find_one = AsyncMock(return_value=None)

        response = await async_client.post(f"/activities/{VALID_OID}/leave")

        assert response.status_code == 404
        assert response.json()["detail"] == "Active membership not found"


# ═════════════════════════════════════════════════════════════════════════════
# LIST MEMBERS
# ═════════════════════════════════════════════════════════════════════════════


class TestListMembers:
    """GET /activities/{activity_id}/members"""

    async def test_list_members_as_regular_user(
        self, async_client, mock_mongo, mock_membership_col, mock_db
    ):
        """Regular user only sees approved members."""
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=99))

        approved_member = _make_membership(user_id=2, membership_status="approved")
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[approved_member])
        mock_membership_col.find = MagicMock(return_value=mock_cursor)

        # Mock for SQL user query
        mock_user_obj = MagicMock()
        mock_user_obj.id = 2
        mock_user_obj.username = "member2"
        mock_user_obj.avatar = "avatars/member2.jpg"
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_user_obj]
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await async_client.get(f"/activities/{VALID_OID}/members")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["user_id"] == 2
        assert data["items"][0]["user_preview"]["username"] == "member2"

        # Verify that filter contains ONLY approved
        call_args = mock_membership_col.find.call_args
        status_filter = call_args[0][0]["status"]["$in"]
        assert "approved" in status_filter
        assert "pending" not in status_filter

    async def test_list_members_as_creator(
        self, async_client, mock_mongo, mock_membership_col, mock_db
    ):
        """Creator sees approved + pending members."""
        # creator_id == current_user.id (1) -> sees pending too
        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=1))

        members = [
            _make_membership(user_id=2, membership_status="approved"),
            _make_membership(
                user_id=3,
                membership_status="pending",
                membership_id=str(ObjectId()),
            ),
        ]
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=members)
        mock_membership_col.find = MagicMock(return_value=mock_cursor)

        mock_user2 = MagicMock(id=2, username="member2", avatar=None)
        mock_user3 = MagicMock(id=3, username="member3", avatar=None)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_user2, mock_user3]
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await async_client.get(f"/activities/{VALID_OID}/members")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

        # Verify that filter contains approved + pending
        call_args = mock_membership_col.find.call_args
        status_filter = call_args[0][0]["status"]["$in"]
        assert "approved" in status_filter
        assert "pending" in status_filter

    async def test_list_members_as_moderator(
        self, async_client, mock_mongo, mock_membership_col, mock_db
    ):
        """Moderator sees approved + pending even for other activities."""
        mod_user = _make_user(user_id=1, role=UserRole.moderator)
        app.dependency_overrides[get_current_user] = lambda: mod_user

        mock_mongo.find_one = AsyncMock(return_value=_make_activity(creator_id=99))
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_membership_col.find = MagicMock(return_value=mock_cursor)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await async_client.get(f"/activities/{VALID_OID}/members")

        assert response.status_code == 200

        # Moderator sees approved + pending
        call_args = mock_membership_col.find.call_args
        status_filter = call_args[0][0]["status"]["$in"]
        assert "approved" in status_filter
        assert "pending" in status_filter

    async def test_list_members_activity_not_found(
        self, async_client, mock_mongo, mock_membership_col
    ):
        mock_mongo.find_one = AsyncMock(return_value=None)

        response = await async_client.get(f"/activities/{VALID_OID}/members")

        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"


# ═════════════════════════════════════════════════════════════════════════════
# GET MY MEMBERSHIP
# ═════════════════════════════════════════════════════════════════════════════


class TestGetMyMembership:
    """GET /activities/{activity_id}/members/me"""

    async def test_get_my_membership_found(self, async_client, mock_membership_col):
        membership = _make_membership(user_id=1, membership_status="approved")
        mock_membership_col.find_one = AsyncMock(return_value=membership)

        response = await async_client.get(f"/activities/{VALID_OID}/members/me")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 1
        assert data["status"] == "approved"

    async def test_get_my_membership_not_found(self, async_client, mock_membership_col):
        mock_membership_col.find_one = AsyncMock(return_value=None)

        response = await async_client.get(f"/activities/{VALID_OID}/members/me")

        assert response.status_code == 200
        assert response.json() is None

    async def test_get_my_membership_invalid_id(self, async_client):
        response = await async_client.get("/activities/not-valid/members/me")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid activity id"
