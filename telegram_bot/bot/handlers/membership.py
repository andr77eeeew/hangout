import html
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from bot.api_client import APIClient
from bot.keyboards.inline import (
    get_membership_action_keyboard,
    get_kick_confirmation_keyboard,
)

router = Router()


@router.message(Command("join"))
async def cmd_join(
    message: Message,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not linked_user or "id" not in linked_user:
        await message.answer("❌ You must link your account first using /link.")
        return

    user_id = int(linked_user["id"])
    args = message.text.strip().split() if message.text else []
    if len(args) < 2:
        await message.answer(
            "⚠️ Please provide an activity ID.\nUsage: <code>/join &lt;activity_id&gt;</code>",
            parse_mode="HTML",
        )
        return

    activity_id = args[1]
    try:
        membership = await client.join_activity(
            user_id=user_id, activity_id=activity_id
        )
        if membership.status == "approved":
            response_text = (
                "✅ <b>Successfully joined!</b> You are now a member of the activity."
            )
        elif membership.status == "pending":
            response_text = "⏳ <b>Request Sent!</b> Your request to join is pending approval from the activity creator."
        else:
            response_text = f"ℹ️ Membership request status: <b>{membership.status}</b>"

        await message.answer(response_text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Failed to join activity: {str(e)}")


@router.callback_query(F.data.startswith("join_act:"))
async def handle_join_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not callback.data:
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    user_id = int(linked_user["id"])
    activity_id = callback.data.split(":")[1]

    try:
        membership = await client.join_activity(
            user_id=user_id, activity_id=activity_id
        )
        if membership.status == "approved":
            response_text = (
                "✅ <b>Successfully joined!</b> You are now a member of the activity."
            )
        elif membership.status == "pending":
            response_text = "⏳ <b>Request Sent!</b> Your request to join is pending approval from the activity creator."
        else:
            response_text = f"ℹ️ Membership request status: <b>{membership.status}</b>"

        if isinstance(callback.message, Message):
            await callback.message.reply(response_text, parse_mode="HTML")
        await callback.answer("Request processed!")
    except Exception as e:
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@router.message(Command("pending"))
async def cmd_pending(
    message: Message,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not linked_user or "id" not in linked_user:
        await message.answer("❌ You must link your account first using /link.")
        return

    user_id = int(linked_user["id"])
    try:
        activities = await client.get_my_created_activities(user_id)
        if not activities:
            await message.answer("📂 You haven't created any activities yet.")
            return

        total_pending = 0
        for act in activities:
            pending = await client.get_pending_members(user_id, act.id)
            for memb in pending:
                total_pending += 1
                username = (
                    memb.user_preview.username
                    if memb.user_preview
                    else f"User {memb.user_id}"
                )
                text = (
                    f"👤 <b>Join Request</b>\n\n"
                    f"<b>Activity:</b> {html.escape(act.title)}\n"
                    f"<b>User:</b> @{html.escape(username)}\n"
                    f"<b>Requested:</b> {memb.joined_at.strftime('%Y-%m-%d %H:%M')}"
                )
                keyboard = get_membership_action_keyboard(memb.id)
                await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

        if total_pending == 0:
            await message.answer(
                "📂 You have no pending membership requests at the moment."
            )
    except Exception as e:
        await message.answer(f"❌ Failed to retrieve pending requests: {str(e)}")


@router.callback_query(F.data.startswith("pending_members:"))
async def handle_pending_members_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not callback.data:
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    user_id = int(linked_user["id"])
    activity_id = callback.data.split(":")[1]

    try:
        activity = await client.get_internal_activity(activity_id)
        if activity.creator_id != user_id:
            await callback.answer(
                "❌ You are not the creator of this activity.", show_alert=True
            )
            return

        pending = await client.get_pending_members(user_id, activity_id)
        if not pending:
            await callback.answer(
                "📂 No pending membership requests for this activity.", show_alert=True
            )
            return

        await callback.answer()
        for memb in pending:
            username = (
                memb.user_preview.username
                if memb.user_preview
                else f"User {memb.user_id}"
            )
            text = (
                f"👤 <b>Join Request</b>\n\n"
                f"<b>Activity:</b> {html.escape(activity.title)}\n"
                f"<b>User:</b> @{html.escape(username)}\n"
                f"<b>Requested:</b> {memb.joined_at.strftime('%Y-%m-%d %H:%M')}"
            )
            keyboard = get_membership_action_keyboard(memb.id)
            if isinstance(callback.message, Message):
                await callback.message.answer(
                    text, reply_markup=keyboard, parse_mode="HTML"
                )
    except Exception as e:
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("approve:"))
async def handle_approve_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not callback.data:
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    user_id = int(linked_user["id"])
    membership_id = callback.data.split(":")[1]

    try:
        await client.approve_member(user_id, membership_id)
        await callback.answer("✅ Request approved successfully!")
        if isinstance(callback.message, Message):
            current_text = callback.message.html_text if callback.message.text else ""
            new_text = f"{current_text}\n\n✅ <b>Approved</b>"
            await callback.message.edit_text(
                new_text, reply_markup=None, parse_mode="HTML"
            )
    except Exception as e:
        await callback.answer(f"❌ Failed to approve: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("reject:"))
async def handle_reject_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not callback.data:
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    user_id = int(linked_user["id"])
    membership_id = callback.data.split(":")[1]

    try:
        await client.reject_member(user_id, membership_id)
        await callback.answer("❌ Request rejected.")
        if isinstance(callback.message, Message):
            current_text = callback.message.html_text if callback.message.text else ""
            new_text = f"{current_text}\n\n❌ <b>Rejected</b>"
            await callback.message.edit_text(
                new_text, reply_markup=None, parse_mode="HTML"
            )
    except Exception as e:
        await callback.answer(f"❌ Failed to reject: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("kick:"))
async def handle_kick_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not callback.data:
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    membership_id = callback.data.split(":")[1]
    keyboard = get_kick_confirmation_keyboard(membership_id)

    if isinstance(callback.message, Message):
        current_text = callback.message.html_text if callback.message.text else ""
        new_text = (
            f"{current_text}\n\n⚠️ <b>Are you sure you want to kick this member?</b>"
        )
        await callback.message.edit_text(
            new_text, reply_markup=keyboard, parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_kick:"))
async def handle_confirm_kick_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not callback.data:
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    user_id = int(linked_user["id"])
    membership_id = callback.data.split(":")[1]

    try:
        await client.kick_member(user_id, membership_id)
        await callback.answer("👢 Member kicked successfully.")
        if isinstance(callback.message, Message):
            current_text = callback.message.html_text if callback.message.text else ""
            if "⚠️ <b>Are you sure you want to kick this member?</b>" in current_text:
                current_text = current_text.replace(
                    "\n\n⚠️ <b>Are you sure you want to kick this member?</b>", ""
                )
            new_text = f"{current_text}\n\n👢 <b>Kicked</b>"
            await callback.message.edit_text(
                new_text, reply_markup=None, parse_mode="HTML"
            )
    except Exception as e:
        await callback.answer(f"❌ Failed to kick member: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("cancel_kick:"))
async def handle_cancel_kick_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not callback.data:
        await callback.answer()
        return

    await callback.answer("❌ Kick cancelled.")
    if isinstance(callback.message, Message):
        current_text = callback.message.html_text if callback.message.text else ""
        if "⚠️ <b>Are you sure you want to kick this member?</b>" in current_text:
            current_text = current_text.replace(
                "\n\n⚠️ <b>Are you sure you want to kick this member?</b>", ""
            )
        await callback.message.edit_text(
            current_text, reply_markup=None, parse_mode="HTML"
        )
