from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from bson import ObjectId
from sqlalchemy.ext.asyncio import AsyncSession
from pymongo.asynchronous.collection import AsyncCollection

from app.models.user import User
from app.models.notification_preferences import NotificationPreferences
from app.services.membership import MembershipService
from app.tasks.notifications import notify_membership_change_task

VALID_OID = str(ObjectId())
VALID_MEMBERSHIP_OID = str(ObjectId())


def _make_activity(
    *,
    creator_id: int = 99,
    status: str = "active",
    activity_type: str = "closed",
    max_members: int = 10,
    current_members: int = 1,
) -> dict:
    return {
        "_id": ObjectId(VALID_OID),
        "title": "Board Games",
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
    membership_status: str = "pending",
) -> dict:
    return {
        "_id": ObjectId(membership_id or VALID_MEMBERSHIP_OID),
        "activity_id": ObjectId(activity_id or VALID_OID),
        "user_id": user_id,
        "status": membership_status,
        "joined_at": datetime.now(timezone.utc),
    }


@pytest.mark.asyncio
async def test_join_closed_activity_triggers_notification_task() -> None:
    """Applying to a closed activity triggers notify_membership_change_task with 'applied' change_type."""
    activities_col = AsyncMock(spec=AsyncCollection)
    membership_col = AsyncMock(spec=AsyncCollection)

    # Setup activity as closed
    activity = _make_activity(creator_id=99, activity_type="closed")
    activities_col.find_one = AsyncMock(return_value=activity)

    inserted_id = ObjectId()
    membership_col.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id=inserted_id)
    )

    created_membership = _make_membership(
        membership_id=str(inserted_id),
        activity_id=VALID_OID,
        user_id=1,
        membership_status="pending",
    )
    membership_col.find_one = AsyncMock(return_value=created_membership)

    with patch(
        "app.tasks.notifications.notify_membership_change_task.delay"
    ) as mock_delay:
        await MembershipService.join_activity(
            user_id=1,
            activity_id=VALID_OID,
            activities_col=activities_col,
            membership_col=membership_col,
        )

        mock_delay.assert_called_once_with(
            user_id=99, activity_title="Board Games", change_type="applied"
        )


@pytest.mark.asyncio
async def test_approve_member_triggers_notification_task() -> None:
    """Approving a pending member triggers notify_membership_change_task with 'approved' change_type."""
    activities_col = AsyncMock(spec=AsyncCollection)
    membership_col = AsyncMock(spec=AsyncCollection)

    membership = _make_membership(
        membership_id=VALID_MEMBERSHIP_OID,
        activity_id=VALID_OID,
        user_id=2,
        membership_status="pending",
    )
    membership_col.find_one = AsyncMock(return_value=membership)

    activity = _make_activity(creator_id=99, activity_type="closed")
    activities_col.find_one = AsyncMock(return_value=activity)
    activities_col.find_one_and_update = AsyncMock(return_value=activity)

    updated_membership = _make_membership(
        membership_id=VALID_MEMBERSHIP_OID,
        activity_id=VALID_OID,
        user_id=2,
        membership_status="approved",
    )
    membership_col.find_one_and_update = AsyncMock(return_value=updated_membership)

    with patch(
        "app.tasks.notifications.notify_membership_change_task.delay"
    ) as mock_delay:
        await MembershipService.approve_member(
            user_id=99,
            is_moderator=False,
            membership_id=VALID_MEMBERSHIP_OID,
            activities_col=activities_col,
            membership_col=membership_col,
        )

        mock_delay.assert_called_once_with(
            user_id=2, activity_title="Board Games", change_type="approved"
        )


@pytest.mark.asyncio
async def test_reject_member_triggers_notification_task() -> None:
    """Rejecting a pending member triggers notify_membership_change_task with 'rejected' change_type."""
    activities_col = AsyncMock(spec=AsyncCollection)
    membership_col = AsyncMock(spec=AsyncCollection)

    membership = _make_membership(
        membership_id=VALID_MEMBERSHIP_OID,
        activity_id=VALID_OID,
        user_id=2,
        membership_status="pending",
    )
    membership_col.find_one = AsyncMock(return_value=membership)

    activity = _make_activity(creator_id=99, activity_type="closed")
    activities_col.find_one = AsyncMock(return_value=activity)

    updated_membership = _make_membership(
        membership_id=VALID_MEMBERSHIP_OID,
        activity_id=VALID_OID,
        user_id=2,
        membership_status="rejected",
    )
    membership_col.find_one_and_update = AsyncMock(return_value=updated_membership)

    with patch(
        "app.tasks.notifications.notify_membership_change_task.delay"
    ) as mock_delay:
        await MembershipService.reject_member(
            user_id=99,
            is_moderator=False,
            membership_id=VALID_MEMBERSHIP_OID,
            activities_col=activities_col,
            membership_col=membership_col,
        )

        mock_delay.assert_called_once_with(
            user_id=2, activity_title="Board Games", change_type="rejected"
        )


@pytest.mark.asyncio
async def test_kick_member_triggers_notification_task() -> None:
    """Kicking an approved member triggers notify_membership_change_task with 'kicked' change_type."""
    activities_col = AsyncMock(spec=AsyncCollection)
    membership_col = AsyncMock(spec=AsyncCollection)

    membership = _make_membership(
        membership_id=VALID_MEMBERSHIP_OID,
        activity_id=VALID_OID,
        user_id=2,
        membership_status="approved",
    )
    membership_col.find_one = AsyncMock(return_value=membership)

    activity = _make_activity(creator_id=99, activity_type="closed")
    activities_col.find_one = AsyncMock(return_value=activity)
    activities_col.find_one_and_update = AsyncMock(return_value=activity)

    updated_membership = _make_membership(
        membership_id=VALID_MEMBERSHIP_OID,
        activity_id=VALID_OID,
        user_id=2,
        membership_status="kicked",
    )
    membership_col.find_one_and_update = AsyncMock(return_value=updated_membership)

    with patch(
        "app.tasks.notifications.notify_membership_change_task.delay"
    ) as mock_delay:
        await MembershipService.kick_member(
            user_id=99,
            is_moderator=False,
            membership_id=VALID_MEMBERSHIP_OID,
            activities_col=activities_col,
            membership_col=membership_col,
        )

        mock_delay.assert_called_once_with(
            user_id=2, activity_title="Board Games", change_type="kicked"
        )


def test_notify_membership_change_task_resolves_successfully() -> None:
    """Task resolves correctly, checks preferences, and invokes notification client properly."""
    # Setup mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_sessionmaker = MagicMock()
    mock_sessionmaker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_sessionmaker.return_value.__aexit__ = AsyncMock()

    # Mock user query return values
    active_user = User(id=1, is_active=True, telegram_id="12345")
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = active_user
    mock_db.execute.return_value = user_result

    # Mock preference checks
    prefs = NotificationPreferences(user_id=1, membership_updates=True)

    with (
        patch("app.tasks.notifications.AsyncSessionLocal", mock_sessionmaker),
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs,
        ) as mock_prefs,
        patch(
            "app.services.notification.NotificationService.send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send_tg,
    ):
        # Execute the Celery task synchronously
        notify_membership_change_task.run(
            user_id=1, activity_title="Hiking", change_type="approved"
        )

        # Assert preferences were checked lazy-on-read
        mock_prefs.assert_called_once_with(1, mock_db)

        # Assert correct message is delivered
        mock_send_tg.assert_called_once_with(
            "12345",
            "Your request to join the activity <b>Hiking</b> has been <b>approved</b>! 🎉",
        )


def test_notify_membership_change_task_respects_disabled_preference() -> None:
    """Task respects disabled notification preferences and skips sending telegram messages."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_sessionmaker = MagicMock()
    mock_sessionmaker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_sessionmaker.return_value.__aexit__ = AsyncMock()

    active_user = User(id=1, is_active=True, telegram_id="12345")
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = active_user
    mock_db.execute.return_value = user_result

    prefs = NotificationPreferences(user_id=1, membership_updates=False)

    with (
        patch("app.tasks.notifications.AsyncSessionLocal", mock_sessionmaker),
        patch(
            "app.services.notification_preferences.NotificationPreferencesService.get_preferences",
            return_value=prefs,
        ),
        patch(
            "app.services.notification.NotificationService.send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send_tg,
    ):
        notify_membership_change_task.run(
            user_id=1, activity_title="Hiking", change_type="approved"
        )

        mock_send_tg.assert_not_called()
