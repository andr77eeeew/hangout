from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from bot.api_client import APIClient
from bot.filters.moderator import ModeratorFilter
from bot.handlers.activities import (
    cmd_my_activities,
    handle_my_acts_callback,
    cmd_my_memberships,
    handle_my_membs_callback,
    cmd_activity,
    cmd_create_activity,
    handle_category_selected,
    handle_type_selected,
    handle_format_selected,
    process_title,
    process_description,
    process_date,
    process_extra_data,
    process_max_members,
    process_tags,
    handle_confirm_create,
    cmd_cancel,
    handle_cancel_callback,
)
from bot.handlers.membership import (
    cmd_join,
    handle_join_callback,
    cmd_pending,
    handle_approve_callback,
    handle_reject_callback,
    handle_kick_callback,
    handle_confirm_kick_callback,
    handle_cancel_kick_callback,
)
from bot.handlers.tags import (
    cmd_my_tags,
    cmd_add_tag,
    cmd_remove_tag,
    handle_remove_tag_callback,
)
from bot.handlers.moderation import (
    cmd_reports,
    handle_reports_page_callback,
    handle_view_report_callback,
    handle_take_report_callback,
    handle_resolve_report_callback,
    process_resolve_resolution,
    handle_skip_notes_callback,
    process_resolve_notes,
    handle_ban_decision_callback,
    handle_confirm_resolve_callback,
    handle_dismiss_report_callback,
    process_dismiss_resolution,
    handle_skip_dismiss_notes_callback,
    process_dismiss_notes,
    handle_confirm_dismiss_callback,
    cmd_ban,
    process_ban_user_id,
    process_ban_reason,
    handle_confirm_ban_callback,
    cmd_unban,
    process_unban_user_id,
    process_unban_reason,
    handle_confirm_unban_callback,
)
from bot.states.activity import ActivityForm
from bot.states.moderation import (
    ResolveReportForm,
    DismissReportForm,
    BanForm,
    UnbanForm,
)
from bot.schemas import (
    ActivityDetails,
    MembershipSummary,
    MemberPreview,
    TagSummary,
    ReportDetails,
    ReportPage,
)


def get_mock_message() -> AsyncMock:
    msg = AsyncMock(spec=Message)
    msg.text = ""
    msg.answer = AsyncMock()
    msg.reply = AsyncMock()
    msg.delete = AsyncMock()
    msg.edit_text = AsyncMock()
    msg.edit_reply_markup = AsyncMock()
    return msg


def get_mock_callback(data: str) -> AsyncMock:
    cb = AsyncMock(spec=CallbackQuery)
    cb.data = data
    cb.answer = AsyncMock()
    cb.message = get_mock_message()
    return cb


# --- Activities Tests ---


@pytest.mark.asyncio
async def test_cmd_my_activities_success() -> None:
    message = get_mock_message()
    client = AsyncMock(spec=APIClient)
    client.get_user_created_activities.return_value = []

    linked_user = {"id": 1, "username": "testuser"}
    await cmd_my_activities(message, client, linked_user=linked_user)

    client.get_user_created_activities.assert_called_once_with(1)
    message.answer.assert_called_once()
    assert "You haven't created any activities yet" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_my_acts_callback_success() -> None:
    callback = get_mock_callback("my_acts:1")
    client = AsyncMock(spec=APIClient)
    client.get_user_created_activities.return_value = []

    linked_user = {"id": 1, "username": "testuser"}
    await handle_my_acts_callback(callback, client, linked_user=linked_user)

    client.get_user_created_activities.assert_called_once_with(1)
    callback.message.edit_text.assert_called_once()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_my_memberships_success() -> None:
    message = get_mock_message()
    client = AsyncMock(spec=APIClient)
    client.get_user_joined_activities.return_value = []

    linked_user = {"id": 1, "username": "testuser"}
    await cmd_my_memberships(message, client, linked_user=linked_user)

    client.get_user_joined_activities.assert_called_once_with(1)
    message.answer.assert_called_once()
    assert "You haven't joined any activities yet" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_my_membs_callback_success() -> None:
    callback = get_mock_callback("my_membs:1")
    client = AsyncMock(spec=APIClient)
    client.get_user_joined_activities.return_value = []

    linked_user = {"id": 1, "username": "testuser"}
    await handle_my_membs_callback(callback, client, linked_user=linked_user)

    client.get_user_joined_activities.assert_called_once_with(1)
    callback.message.edit_text.assert_called_once()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_activity_success() -> None:
    message = get_mock_message()
    message.text = "/activity 507f1f77bcf86cd799439011"
    client = AsyncMock(spec=APIClient)

    activity = ActivityDetails(
        id="507f1f77bcf86cd799439011",
        creator_id=1,
        title="Gaming",
        description="Let's play!",
        starts_at=datetime.now(timezone.utc),
        ends_at=datetime.now(timezone.utc) + timedelta(hours=2),
        format="online",
        category="games",
        tags=["gaming"],
        current_members=1,
        status="active",
    )
    client.get_internal_activity.return_value = activity

    linked_user = {"id": 1, "username": "testuser"}
    await cmd_activity(message, client, linked_user=linked_user)

    client.get_internal_activity.assert_called_once_with("507f1f77bcf86cd799439011")
    message.answer.assert_called_once()
    assert "Gaming" in message.answer.call_args[0][0]


# --- Activity Creation FSM Tests ---


@pytest.mark.asyncio
async def test_create_activity_fsm_happy_path() -> None:
    message = get_mock_message()
    state = AsyncMock(spec=FSMContext)

    linked_user = {"id": 1, "username": "testuser"}

    # 1. Start FSM flow
    await cmd_create_activity(message, state, linked_user=linked_user)
    state.set_state.assert_called_once_with(ActivityForm.waiting_for_category)
    message.answer.assert_called_once()

    # 2. Select category
    callback = get_mock_callback("category:games")

    await handle_category_selected(callback, state)
    state.update_data.assert_called_once_with(category="games")
    state.set_state.assert_any_call(ActivityForm.waiting_for_type)
    callback.answer.assert_called_once()

    # 3. Select type
    callback = get_mock_callback("type:open")
    await handle_type_selected(callback, state)
    state.update_data.assert_any_call(type="open")
    state.set_state.assert_any_call(ActivityForm.waiting_for_format)

    # 4. Select format
    callback = get_mock_callback("format:online")
    await handle_format_selected(callback, state)
    state.update_data.assert_any_call(format="online")
    state.set_state.assert_any_call(ActivityForm.waiting_for_title)

    # 5. Process title
    message.text = "A Wonderful Activity Title"
    await process_title(message, state)
    state.update_data.assert_any_call(title="A Wonderful Activity Title")
    state.set_state.assert_any_call(ActivityForm.waiting_for_description)

    # 6. Process description
    message.text = "This is a detailed description of the activity."
    await process_description(message, state)
    state.update_data.assert_any_call(
        description="This is a detailed description of the activity."
    )
    state.set_state.assert_any_call(ActivityForm.waiting_for_date)

    # 7. Process date
    future_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime(
        "%Y-%m-%d %H:%M"
    )
    message.text = future_date
    state.get_data.return_value = {"format": "online", "category": "games"}
    await process_date(message, state)
    state.set_state.assert_any_call(ActivityForm.waiting_for_extra_data)

    # 8. Process extra data
    message.text = "Counter-Strike"
    state.get_data.return_value = {"category": "games", "format": "online"}
    await process_extra_data(message, state)
    state.set_state.assert_any_call(ActivityForm.waiting_for_max_members)

    # 9. Process max members
    message.text = "10"
    await process_max_members(message, state)
    state.set_state.assert_any_call(ActivityForm.waiting_for_tags)

    # 10. Process tags
    message.text = "gaming fun cs"
    state.get_data.return_value = {
        "category": "games",
        "type": "open",
        "format": "online",
        "title": "A Wonderful Activity Title",
        "description": "This is a detailed description of the activity.",
        "date": datetime.now(timezone.utc) + timedelta(days=1),
        "location": None,
        "extra_data": {"game_name": "Counter-Strike", "platform": "pc"},
        "max_members": 10,
        "tags": ["gaming", "fun", "cs"],
    }
    await process_tags(message, state)
    state.set_state.assert_any_call(ActivityForm.waiting_for_confirmation)

    # 11. Confirm creation
    callback = get_mock_callback("confirm_create")
    client = AsyncMock(spec=APIClient)
    activity = ActivityDetails(
        id="507f1f77bcf86cd799439011",
        creator_id=1,
        title="Gaming",
        description="Let's play!",
        starts_at=datetime.now(timezone.utc),
        ends_at=datetime.now(timezone.utc) + timedelta(hours=2),
        format="online",
        category="games",
        tags=["gaming"],
        current_members=1,
        status="active",
    )
    client.create_activity.return_value = activity
    await handle_confirm_create(callback, state, client, linked_user=linked_user)
    client.create_activity.assert_called_once()
    state.clear.assert_called_once()
    callback.answer.assert_called_once_with("Created successfully!")


@pytest.mark.asyncio
async def test_create_activity_fsm_cancel() -> None:
    message = get_mock_message()
    state = AsyncMock(spec=FSMContext)

    await cmd_cancel(message, state)
    state.clear.assert_called_once()
    message.answer.assert_called_once_with("❌ Activity creation cancelled.")

    state.clear.reset_mock()
    callback = get_mock_callback("cancel_activity_creation")

    await handle_cancel_callback(callback, state)
    state.clear.assert_called_once()
    callback.message.edit_text.assert_called_once_with(
        "❌ Activity creation cancelled."
    )
    callback.answer.assert_called_once()


# --- Membership Tests ---


@pytest.mark.asyncio
async def test_cmd_join_success() -> None:
    message = get_mock_message()
    message.text = "/join 507f1f77bcf86cd799439011"
    client = AsyncMock(spec=APIClient)

    membership = MembershipSummary(
        id="memb123",
        activity_id="507f1f77bcf86cd799439011",
        user_id=1,
        status="pending",
        joined_at=datetime.now(timezone.utc),
    )
    client.join_activity.return_value = membership

    linked_user = {"id": 1, "username": "testuser"}
    await cmd_join(message, client, linked_user=linked_user)

    client.join_activity.assert_called_once_with(
        user_id=1, activity_id="507f1f77bcf86cd799439011"
    )
    message.answer.assert_called_once()
    assert "pending approval" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_join_callback_success() -> None:
    callback = get_mock_callback("join_act:507f1f77bcf86cd799439011")

    client = AsyncMock(spec=APIClient)
    membership = MembershipSummary(
        id="memb123",
        activity_id="507f1f77bcf86cd799439011",
        user_id=1,
        status="approved",
        joined_at=datetime.now(timezone.utc),
    )
    client.join_activity.return_value = membership

    linked_user = {"id": 1, "username": "testuser"}
    await handle_join_callback(callback, client, linked_user=linked_user)

    client.join_activity.assert_called_once_with(
        user_id=1, activity_id="507f1f77bcf86cd799439011"
    )
    callback.message.reply.assert_called_once()
    callback.answer.assert_called_once_with("Request processed!")


@pytest.mark.asyncio
async def test_cmd_pending_and_inline_callbacks() -> None:
    message = get_mock_message()
    client = AsyncMock(spec=APIClient)

    activity = ActivityDetails(
        id="507f1f77bcf86cd799439011",
        creator_id=1,
        title="Gaming",
        description="Let's play!",
        starts_at=datetime.now(timezone.utc),
        ends_at=datetime.now(timezone.utc) + timedelta(hours=2),
        format="online",
        category="games",
        tags=["gaming"],
        current_members=1,
        status="active",
    )
    client.get_my_created_activities.return_value = [activity]

    membership = MembershipSummary(
        id="memb123",
        activity_id="507f1f77bcf86cd799439011",
        user_id=2,
        status="pending",
        joined_at=datetime.now(timezone.utc),
        user_preview=MemberPreview(id=2, username="otherguy"),
    )
    client.get_pending_members.return_value = [membership]

    linked_user = {"id": 1, "username": "testuser"}
    await cmd_pending(message, client, linked_user=linked_user)

    client.get_my_created_activities.assert_called_once_with(1)
    client.get_pending_members.assert_called_once_with(1, "507f1f77bcf86cd799439011")
    message.answer.assert_called_once()
    assert "Join Request" in message.answer.call_args[0][0]

    # Test approve callback
    callback_approve = get_mock_callback("approve:memb123")
    callback_approve.message.text = "Requested"

    await handle_approve_callback(callback_approve, client, linked_user=linked_user)
    client.approve_member.assert_called_once_with(1, "memb123")
    callback_approve.message.edit_text.assert_called_once()
    callback_approve.answer.assert_called_once_with("✅ Request approved successfully!")

    # Test reject callback
    callback_reject = get_mock_callback("reject:memb123")
    await handle_reject_callback(callback_reject, client, linked_user=linked_user)
    client.reject_member.assert_called_once_with(1, "memb123")
    callback_reject.answer.assert_called_once_with("❌ Request rejected.")

    # Test kick callback
    callback_kick = get_mock_callback("kick:memb123")
    await handle_kick_callback(callback_kick, client, linked_user=linked_user)
    callback_kick.message.edit_text.assert_called()

    # Test confirm kick
    callback_confirm = get_mock_callback("confirm_kick:memb123")
    await handle_confirm_kick_callback(
        callback_confirm, client, linked_user=linked_user
    )
    client.kick_member.assert_called_once_with(1, "memb123")
    callback_confirm.answer.assert_called_once_with("👢 Member kicked successfully.")

    # Test cancel kick
    callback_cancel = get_mock_callback("cancel_kick:memb123")
    await handle_cancel_kick_callback(callback_cancel, client, linked_user=linked_user)
    callback_cancel.answer.assert_called_once_with("❌ Kick cancelled.")


# --- Tag Favorites Tests ---


@pytest.mark.asyncio
async def test_cmd_my_tags_and_management() -> None:
    message = get_mock_message()
    client = AsyncMock(spec=APIClient)

    tag = TagSummary(id=1, name="gaming", slug="gaming")
    client.get_favorite_tags.return_value = [tag]

    linked_user = {"id": 1, "username": "testuser"}
    await cmd_my_tags(message, client, linked_user=linked_user)

    client.get_favorite_tags.assert_called_once_with(1)
    message.answer.assert_called_once()
    assert "Your Favorite Tags" in message.answer.call_args[0][0]

    # Test add tag
    message.text = "/add_tag anime"
    await cmd_add_tag(message, client, linked_user=linked_user)
    client.add_favorite_tag.assert_called_once_with(1, "anime")
    message.answer.assert_any_call(
        "✅ Tag <b>anime</b> successfully added to your favorites!", parse_mode="HTML"
    )

    # Test remove tag command
    message.text = "/remove_tag anime"
    await cmd_remove_tag(message, client, linked_user=linked_user)
    client.remove_favorite_tag.assert_called_once_with(1, "anime")

    # Test remove tag callback
    callback = get_mock_callback("remove_tag:anime")
    client.get_favorite_tags.return_value = [tag]

    await handle_remove_tag_callback(callback, client, linked_user=linked_user)
    callback.answer.assert_called_once_with("Removed tag: anime")


# --- Moderator Filter & Commands Tests ---


@pytest.mark.asyncio
async def test_moderator_filter() -> None:
    filter_obj = ModeratorFilter()

    # Case 1: allowed (moderator)
    event = AsyncMock(spec=Message)
    event.from_user = MagicMock(spec=User)
    event.from_user.id = 12345
    client = AsyncMock(spec=APIClient)
    client.get_user_by_telegram_id.return_value = {"user_role": "moderator"}

    result = await filter_obj(event, client)
    assert result is True

    # Case 2: blocked (regular client)
    client.get_user_by_telegram_id.return_value = {"user_role": "client"}
    event.answer = AsyncMock()

    result = await filter_obj(event, client)
    assert result is False
    event.answer.assert_called_once_with(
        "⚠️ This command is restricted to moderators only."
    )


@pytest.mark.asyncio
async def test_cmd_reports_and_pagination() -> None:
    message = get_mock_message()
    client = AsyncMock(spec=APIClient)
    state = AsyncMock(spec=FSMContext)

    report = ReportDetails(
        id="rep1234567890",
        reporter_id=2,
        reported_user_id=3,
        reason="cheater",
        status="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    page = ReportPage(items=[report], total=1, next_cursor="c1", has_more=True)
    client.list_reports_internal.return_value = page

    linked_user = {"id": 1, "username": "moderator"}
    await cmd_reports(message, client, linked_user=linked_user, state=state)

    client.list_reports_internal.assert_called_once_with(moderator_id=1, status="open")
    state.update_data.assert_called_once_with(reports_cursors={2: "c1"})
    message.answer.assert_called_once()
    assert "Open Reports Queue" in message.answer.call_args[0][0]

    # Handle reports page callback
    callback = get_mock_callback("reports_page:2")

    state.get_data.return_value = {"reports_cursors": {2: "c1"}}
    client.list_reports_internal.reset_mock()
    await handle_reports_page_callback(
        callback, client, linked_user=linked_user, state=state
    )

    client.list_reports_internal.assert_called_once_with(
        moderator_id=1, status="open", cursor="c1"
    )
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_handle_view_and_take_report_callback() -> None:
    callback = get_mock_callback("view_report:rep123")

    client = AsyncMock(spec=APIClient)
    report = ReportDetails(
        id="rep123",
        reporter_id=2,
        reported_user_id=3,
        reason="cheater",
        status="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    client.get_report_internal.return_value = report

    linked_user = {"id": 1, "username": "moderator"}
    await handle_view_report_callback(callback, client, linked_user=linked_user)

    client.get_report_internal.assert_called_once_with("rep123", 1)
    callback.message.edit_text.assert_called_once()
    callback.answer.assert_called_once()

    # Take report
    callback_take = get_mock_callback("take_report:rep123")
    client.take_report_internal.return_value = report
    await handle_take_report_callback(callback_take, client, linked_user=linked_user)
    client.take_report_internal.assert_called_once_with("rep123", 1)
    callback_take.answer.assert_called_once_with("📥 You have taken this report!")


# --- Resolving and Dismissing FSM Flows Tests ---


@pytest.mark.asyncio
async def test_resolve_report_fsm_flow() -> None:
    message = get_mock_message()
    state = AsyncMock(spec=FSMContext)

    # Resolve report FSM trigger
    callback = get_mock_callback("resolve_report:rep123")

    await handle_resolve_report_callback(callback, state)
    state.set_state.assert_called_once_with(ResolveReportForm.waiting_for_resolution)
    callback.answer.assert_called_once()
    state.clear.reset_mock()

    # Enter resolution
    message.text = "Warned user and closed report."
    await process_resolve_resolution(message, state)
    state.update_data.assert_called_with(resolution="Warned user and closed report.")
    state.set_state.assert_any_call(ResolveReportForm.waiting_for_notes)

    # Skip notes
    callback_skip = get_mock_callback("skip_notes")
    state.get_data.return_value = {
        "report_id": "rep123",
        "resolution": "Warning",
        "moderator_notes": "notes",
    }
    await handle_skip_notes_callback(callback_skip, state)
    state.update_data.assert_called_with(moderator_notes=None)
    state.set_state.assert_any_call(ResolveReportForm.waiting_for_ban_decision)

    # Enter notes
    message.text = "Some custom moderator notes."
    await process_resolve_notes(message, state)
    state.update_data.assert_called_with(moderator_notes="Some custom moderator notes.")

    # Ban decision callback (No ban)
    callback_ban = get_mock_callback("ban_decision:no")
    state.get_data.return_value = {
        "report_id": "rep123",
        "resolution": "Warning",
        "moderator_notes": "notes",
    }
    await handle_ban_decision_callback(callback_ban, state)

    # Confirm resolve callback
    callback_confirm = get_mock_callback("confirm_resolve:rep123")
    client = AsyncMock(spec=APIClient)
    report = ReportDetails(
        id="rep123",
        reporter_id=2,
        reported_user_id=3,
        reason="cheater",
        status="resolved",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        resolution="Warning",
        moderator_notes="notes",
    )
    client.resolve_report_internal.return_value = report
    linked_user = {"id": 1, "username": "moderator"}
    state.clear.reset_mock()
    await handle_confirm_resolve_callback(
        callback_confirm, client=client, linked_user=linked_user, state=state
    )
    client.resolve_report_internal.assert_called_once()
    state.clear.assert_called_once()
    callback_confirm.answer.assert_called_once_with(
        "✅ Report resolved successfully!", show_alert=True
    )


@pytest.mark.asyncio
async def test_dismiss_report_fsm_flow() -> None:
    callback = get_mock_callback("dismiss_report:rep123")
    state = AsyncMock(spec=FSMContext)

    await handle_dismiss_report_callback(callback, state)
    state.set_state.assert_called_once_with(DismissReportForm.waiting_for_resolution)
    callback.answer.assert_called_once()
    state.clear.reset_mock()

    message = get_mock_message()
    message.text = "No violation found."
    await process_dismiss_resolution(message, state)
    state.update_data.assert_called_with(resolution="No violation found.")
    state.set_state.assert_any_call(DismissReportForm.waiting_for_notes)

    # Skip dismiss notes
    callback_skip = get_mock_callback("skip_notes")
    state.get_data.return_value = {
        "report_id": "rep123",
        "resolution": "No violation",
        "moderator_notes": "notes",
    }
    await handle_skip_dismiss_notes_callback(callback_skip, state)
    state.update_data.assert_called_with(moderator_notes=None)

    # Custom dismiss notes
    message.text = "Everything looks clean."
    await process_dismiss_notes(message, state)
    state.update_data.assert_called_with(moderator_notes="Everything looks clean.")

    # Confirm dismiss
    callback_confirm = get_mock_callback("confirm_dismiss:rep123")
    client = AsyncMock(spec=APIClient)
    report = ReportDetails(
        id="rep123",
        reporter_id=2,
        reported_user_id=3,
        reason="cheater",
        status="dismissed",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        resolution="No violation found.",
        moderator_notes="Everything looks clean.",
    )
    client.dismiss_report_internal.return_value = report
    linked_user = {"id": 1, "username": "moderator"}
    state.clear.reset_mock()
    await handle_confirm_dismiss_callback(
        callback_confirm, client=client, linked_user=linked_user, state=state
    )
    client.dismiss_report_internal.assert_called_once()
    state.clear.assert_called_once()
    callback_confirm.answer.assert_called_once_with(
        "✅ Report dismissed successfully!", show_alert=True
    )


# --- Ban and Unban State Transitions Tests ---


@pytest.mark.asyncio
async def test_ban_user_fsm_flow() -> None:
    message = get_mock_message()
    message.text = "/ban"
    state = AsyncMock(spec=FSMContext)

    linked_user = {"id": 1, "username": "moderator"}
    await cmd_ban(message, state)
    state.set_state.assert_called_once_with(BanForm.waiting_for_user_id)
    state.clear.reset_mock()

    # Input User ID
    message.text = "2"
    await process_ban_user_id(message, state)
    state.update_data.assert_called_once_with(target_user_id=2)
    state.set_state.assert_any_call(BanForm.waiting_for_reason)

    # Input Reason
    message.text = "Spamming activity feed."
    await process_ban_reason(message, state)
    state.update_data.assert_called_with(reason="Spamming activity feed.")

    # Confirm Ban callback
    callback = get_mock_callback("confirm_ban:2")

    client = AsyncMock(spec=APIClient)
    state.get_data.return_value = {
        "target_user_id": 2,
        "reason": "Spamming activity feed.",
    }
    await handle_confirm_ban_callback(
        callback, state=state, client=client, linked_user=linked_user
    )

    client.ban_user_internal.assert_called_once_with(
        user_id=2, reason="Spamming activity feed.", moderator_id=1
    )
    state.clear.assert_called_once()
    callback.answer.assert_called_once_with("✅ User has been banned!", show_alert=True)


@pytest.mark.asyncio
async def test_unban_user_fsm_flow() -> None:
    message = get_mock_message()
    message.text = "/unban"
    state = AsyncMock(spec=FSMContext)

    linked_user = {"id": 1, "username": "moderator"}
    await cmd_unban(message, state)
    state.set_state.assert_called_once_with(UnbanForm.waiting_for_user_id)
    state.clear.reset_mock()

    # Input User ID
    message.text = "2"
    await process_unban_user_id(message, state)
    state.update_data.assert_called_once_with(target_user_id=2)
    state.set_state.assert_any_call(UnbanForm.waiting_for_reason)

    # Input Reason
    message.text = "Apologized and promise to follow rules."
    await process_unban_reason(message, state)
    state.update_data.assert_called_with(
        reason="Apologized and promise to follow rules."
    )

    # Confirm Unban callback
    callback = get_mock_callback("confirm_unban:2")

    client = AsyncMock(spec=APIClient)
    state.get_data.return_value = {
        "target_user_id": 2,
        "reason": "Apologized and promise to follow rules.",
    }
    await handle_confirm_unban_callback(
        callback, state=state, client=client, linked_user=linked_user
    )

    client.unban_user_internal.assert_called_once_with(
        user_id=2, reason="Apologized and promise to follow rules.", moderator_id=1
    )
    state.clear.assert_called_once()
    callback.answer.assert_called_once_with(
        "✅ User has been unbanned!", show_alert=True
    )
