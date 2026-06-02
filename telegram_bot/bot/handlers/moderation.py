import html
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.api_client import APIClient
from bot.filters.moderator import ModeratorFilter
from bot.keyboards.inline import (
    get_reports_list_keyboard,
    get_report_details_keyboard,
    get_ban_decision_keyboard,
    get_moderation_confirm_keyboard,
)
from bot.schemas import ReportDetails
from bot.states.moderation import (
    ResolveReportForm,
    DismissReportForm,
    BanForm,
    UnbanForm,
)

router = Router()
router.message.filter(ModeratorFilter())
router.callback_query.filter(ModeratorFilter())


def format_report_details(report: ReportDetails) -> str:
    text = (
        f"🛡️ <b>Report Details</b>\n\n"
        f"🆔 <b>Report ID:</b> <code>{report.id}</code>\n"
        f"👤 <b>Reporter ID:</b> <code>{report.reporter_id}</code>\n"
        f"👤 <b>Reported User ID:</b> <code>{report.reported_user_id}</code>\n"
    )
    if report.activity_id:
        text += f"📅 <b>Activity ID:</b> <code>{report.activity_id}</code>\n"
    if report.chat_message_id:
        text += f"💬 <b>Chat Message ID:</b> <code>{report.chat_message_id}</code>\n"
    text += (
        f"⚠️ <b>Reason:</b> {html.escape(report.reason or '')}\n"
        f"📊 <b>Status:</b> <code>{report.status}</code>\n"
    )
    if report.moderator_id:
        text += (
            f"👮 <b>Assigned Moderator:</b> User <code>{report.moderator_id}</code>\n"
        )
    if report.resolution:
        text += f"📝 <b>Resolution:</b> {html.escape(report.resolution)}\n"
    if report.moderator_notes:
        text += f"📓 <b>Notes:</b> {html.escape(report.moderator_notes)}\n"

    text += (
        f"🕒 <b>Created At:</b> {report.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    )
    if report.taken_at:
        text += (
            f"🕒 <b>Taken At:</b> {report.taken_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        )
    if report.resolved_at:
        text += f"🕒 <b>Resolved At:</b> {report.resolved_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    return text


@router.message(Command("reports"))
async def cmd_reports(
    message: Message,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
    state: FSMContext | None = None,
) -> None:
    if not linked_user or "id" not in linked_user:
        await message.answer("❌ Account link required.")
        return

    moderator_id = int(linked_user["id"])
    try:
        page = await client.list_reports_internal(
            moderator_id=moderator_id, status="open"
        )
        if not page.items:
            await message.answer("📂 No open reports found.")
            return

        text = "🛡️ <b>Open Reports Queue</b>\n\n"
        for idx, report in enumerate(page.items, start=1):
            text += f"{idx}. <b>Report #{report.id[:8]}</b>\n"
            text += f"   • Reason: {html.escape(report.reason or '')}\n"
            text += f"   • Reporter: User {report.reporter_id}\n"
            text += f"   • Reported: User {report.reported_user_id}\n\n"

        if state:
            await state.update_data(reports_cursors={2: page.next_cursor})

        keyboard = get_reports_list_keyboard(page.items, page=1, has_more=page.has_more)
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Failed to load reports: {str(e)}")


@router.callback_query(F.data.startswith("reports_page:"))
async def handle_reports_page_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
    state: FSMContext | None = None,
) -> None:
    if (
        not callback.data
        or not callback.message
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    moderator_id = int(linked_user["id"])
    page_num = int(callback.data.split(":")[1])

    cursor = None
    cursors: dict[int, str | None] = {}
    if state:
        state_data = await state.get_data()
        cursors = state_data.get("reports_cursors", {})
        cursor = cursors.get(page_num)

    try:
        page = await client.list_reports_internal(
            moderator_id=moderator_id,
            status="open",
            cursor=cursor,
        )
        if not page.items:
            await callback.answer("📂 No more reports on this page.", show_alert=True)
            return

        text = f"🛡️ <b>Open Reports Queue (Page {page_num})</b>\n\n"
        for idx, report in enumerate(page.items, start=1):
            text += f"{idx}. <b>Report #{report.id[:8]}</b>\n"
            text += f"   • Reason: {html.escape(report.reason or '')}\n"
            text += f"   • Reporter: User {report.reporter_id}\n"
            text += f"   • Reported: User {report.reported_user_id}\n\n"

        if state and page.next_cursor:
            cursors[page_num + 1] = page.next_cursor
            await state.update_data(reports_cursors=cursors)

        keyboard = get_reports_list_keyboard(
            page.items, page=page_num, has_more=page.has_more
        )
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("view_report:"))
async def handle_view_report_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if (
        not callback.data
        or not callback.message
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    moderator_id = int(linked_user["id"])
    report_id = callback.data.split(":")[1]

    try:
        report = await client.get_report_internal(report_id, moderator_id)
        text = format_report_details(report)
        keyboard = get_report_details_keyboard(report, moderator_id)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("take_report:"))
async def handle_take_report_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if (
        not callback.data
        or not callback.message
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    moderator_id = int(linked_user["id"])
    report_id = callback.data.split(":")[1]

    try:
        report = await client.take_report_internal(report_id, moderator_id)
        text = format_report_details(report)
        keyboard = get_report_details_keyboard(report, moderator_id)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("📥 You have taken this report!")
    except Exception as e:
        await callback.answer(f"❌ Failed to take report: {str(e)}", show_alert=True)


# --- Resolve Report FSM ---


@router.message(Command("resolve"))
async def cmd_resolve_report(
    message: Message,
    state: FSMContext,
) -> None:
    args = message.text.strip().split() if message.text else []
    if len(args) < 2:
        await message.answer(
            "⚠️ Please provide a report ID.\nUsage: <code>/resolve &lt;report_id&gt;</code>",
            parse_mode="HTML",
        )
        return

    report_id = args[1]
    await start_resolve_flow(message, state, report_id)


@router.callback_query(F.data.startswith("resolve_report:"))
async def handle_resolve_report_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if (
        not callback.data
        or not callback.message
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    report_id = callback.data.split(":")[1]
    await callback.answer()
    await start_resolve_flow(callback.message, state, report_id)


async def start_resolve_flow(
    message: Message, state: FSMContext, report_id: str
) -> None:
    await state.clear()
    await state.update_data(report_id=report_id)
    await state.set_state(ResolveReportForm.waiting_for_resolution)
    await message.answer("📝 Please enter the resolution description for this report:")


@router.message(ResolveReportForm.waiting_for_resolution)
async def process_resolve_resolution(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer(
            "⚠️ Resolution text must not be empty. Please enter the resolution:"
        )
        return

    await state.update_data(resolution=message.text.strip())
    await state.set_state(ResolveReportForm.waiting_for_notes)

    skip_kb = InlineKeyboardBuilder()
    skip_kb.button(text="Skip ➡️", callback_data="skip_notes")
    await message.answer(
        "📓 Please enter any additional notes for other moderators (optional):",
        reply_markup=skip_kb.as_markup(),
    )


@router.callback_query(ResolveReportForm.waiting_for_notes, F.data == "skip_notes")
async def handle_skip_notes_callback(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await callback.answer("Notes skipped.")
    await state.update_data(moderator_notes=None)
    await transition_to_ban_decision(callback.message, state)


@router.message(ResolveReportForm.waiting_for_notes)
async def process_resolve_notes(message: Message, state: FSMContext) -> None:
    notes = message.text.strip() if message.text else ""
    await state.update_data(moderator_notes=notes if notes else None)
    await transition_to_ban_decision(message, state)


async def transition_to_ban_decision(
    message: Message | None, state: FSMContext
) -> None:
    if not message:
        return
    await state.set_state(ResolveReportForm.waiting_for_ban_decision)
    await message.answer(
        "🚫 Should we also ban the reported user?",
        reply_markup=get_ban_decision_keyboard(),
    )


@router.callback_query(
    ResolveReportForm.waiting_for_ban_decision, F.data.startswith("ban:")
)
async def handle_ban_decision_callback(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return

    decision = callback.data.split(":")[1]
    await callback.answer()

    if decision == "yes":
        await state.update_data(ban_user=True)
        await state.set_state(ResolveReportForm.waiting_for_ban_reason)
        await callback.message.answer(
            "🚫 Please enter the reason for banning the user:"
        )
    else:
        await state.update_data(ban_user=False, ban_reason=None)
        await show_resolve_confirmation(callback.message, state)


async def show_resolve_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    report_id = data["report_id"]
    resolution = data["resolution"]
    notes = data.get("moderator_notes") or "None"
    ban_user = data.get("ban_user", False)
    ban_reason = data.get("ban_reason") or "N/A"

    summary = (
        f"🔍 <b>Confirm Report Resolution</b>\n\n"
        f"🆔 <b>Report ID:</b> <code>{report_id}</code>\n"
        f"📝 <b>Resolution:</b> {html.escape(resolution)}\n"
        f"📓 <b>Notes:</b> {html.escape(notes)}\n"
        f"🚫 <b>Ban User?</b> {'Yes' if ban_user else 'No'}\n"
    )
    if ban_user:
        summary += f"⚠️ <b>Ban Reason:</b> {html.escape(ban_reason)}\n"

    keyboard = get_moderation_confirm_keyboard("resolve", report_id)
    await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")


@router.message(ResolveReportForm.waiting_for_ban_reason)
async def process_resolve_ban_reason(message: Message, state: FSMContext) -> None:
    reason = message.text.strip() if message.text else ""
    if not reason:
        await message.answer("⚠️ Ban reason must not be empty. Please enter the reason:")
        return

    await state.update_data(ban_reason=reason)
    await show_resolve_confirmation(message, state)


@router.callback_query(F.data.startswith("confirm_resolve:"))
async def handle_confirm_resolve_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
    state: FSMContext | None = None,
) -> None:
    if (
        not callback.data
        or not callback.message
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    moderator_id = int(linked_user["id"])
    report_id = callback.data.split(":")[1]

    if not state:
        await callback.answer("❌ FSM state lost.", show_alert=True)
        return

    data = await state.get_data()
    if data.get("report_id") != report_id:
        await callback.answer("❌ Report mismatch.", show_alert=True)
        return

    try:
        from bot.schemas import ReportResolvePayload

        payload = ReportResolvePayload(
            resolution=data["resolution"],
            moderator_notes=data.get("moderator_notes"),
            ban_user=data.get("ban_user", False),
            ban_reason=data.get("ban_reason"),
        )
        await client.resolve_report_internal(
            report_id=report_id,
            payload=payload,
            moderator_id=moderator_id,
        )
        await callback.answer("✅ Report resolved successfully!", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "🎉 <b>Success:</b> Report has been resolved.", parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        await callback.message.answer(f"❌ Failed to resolve report: {str(e)}")
        await callback.answer()


@router.callback_query(F.data.startswith("cancel_resolve:"))
async def handle_cancel_resolve_callback(
    callback: CallbackQuery,
    state: FSMContext | None = None,
) -> None:
    if not callback.message:
        await callback.answer()
        return

    await callback.answer("Dismissed.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Resolution flow cancelled.")
    if state:
        await state.clear()


# --- Dismiss Report FSM ---


@router.message(Command("dismiss"))
async def cmd_dismiss_report(
    message: Message,
    state: FSMContext,
) -> None:
    args = message.text.strip().split() if message.text else []
    if len(args) < 2:
        await message.answer(
            "⚠️ Please provide a report ID.\nUsage: <code>/dismiss &lt;report_id&gt;</code>",
            parse_mode="HTML",
        )
        return

    report_id = args[1]
    await start_dismiss_flow(message, state, report_id)


@router.callback_query(F.data.startswith("dismiss_report:"))
async def handle_dismiss_report_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if (
        not callback.data
        or not callback.message
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    report_id = callback.data.split(":")[1]
    await callback.answer()
    await start_dismiss_flow(callback.message, state, report_id)


async def start_dismiss_flow(
    message: Message, state: FSMContext, report_id: str
) -> None:
    await state.clear()
    await state.update_data(report_id=report_id)
    await state.set_state(DismissReportForm.waiting_for_resolution)
    await message.answer("📝 Please enter the dismissal resolution description:")


@router.message(DismissReportForm.waiting_for_resolution)
async def process_dismiss_resolution(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer(
            "⚠️ Resolution text must not be empty. Please enter the resolution:"
        )
        return

    await state.update_data(resolution=message.text.strip())
    await state.set_state(DismissReportForm.waiting_for_notes)

    skip_kb = InlineKeyboardBuilder()
    skip_kb.button(text="Skip ➡️", callback_data="skip_dismiss_notes")
    await message.answer(
        "📓 Please enter any additional notes for other moderators (optional):",
        reply_markup=skip_kb.as_markup(),
    )


@router.callback_query(
    DismissReportForm.waiting_for_notes, F.data == "skip_dismiss_notes"
)
async def handle_skip_dismiss_notes_callback(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await callback.answer("Notes skipped.")
    await state.update_data(moderator_notes=None)
    await show_dismiss_confirmation(callback.message, state)


@router.message(DismissReportForm.waiting_for_notes)
async def process_dismiss_notes(message: Message, state: FSMContext) -> None:
    notes = message.text.strip() if message.text else ""
    await state.update_data(moderator_notes=notes if notes else None)
    await show_dismiss_confirmation(message, state)


async def show_dismiss_confirmation(message: Message | None, state: FSMContext) -> None:
    if not message:
        return
    data = await state.get_data()
    report_id = data["report_id"]
    resolution = data["resolution"]
    notes = data.get("moderator_notes") or "None"

    summary = (
        f"🔍 <b>Confirm Report Dismissal</b>\n\n"
        f"🆔 <b>Report ID:</b> <code>{report_id}</code>\n"
        f"📝 <b>Dismissal Resolution:</b> {html.escape(resolution)}\n"
        f"📓 <b>Notes:</b> {html.escape(notes)}\n"
    )

    keyboard = get_moderation_confirm_keyboard("dismiss", report_id)
    await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_dismiss:"))
async def handle_confirm_dismiss_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
    state: FSMContext | None = None,
) -> None:
    if (
        not callback.data
        or not callback.message
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    moderator_id = int(linked_user["id"])
    report_id = callback.data.split(":")[1]

    if not state:
        await callback.answer("❌ FSM state lost.", show_alert=True)
        return

    data = await state.get_data()
    if data.get("report_id") != report_id:
        await callback.answer("❌ Report mismatch.", show_alert=True)
        return

    try:
        from bot.schemas import ReportDismissPayload

        payload = ReportDismissPayload(
            resolution=data["resolution"],
            moderator_notes=data.get("moderator_notes"),
        )
        await client.dismiss_report_internal(
            report_id=report_id,
            payload=payload,
            moderator_id=moderator_id,
        )
        await callback.answer("✅ Report dismissed successfully!", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "🎉 <b>Success:</b> Report has been dismissed.", parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        await callback.message.answer(f"❌ Failed to dismiss report: {str(e)}")
        await callback.answer()


@router.callback_query(F.data.startswith("cancel_dismiss:"))
async def handle_cancel_dismiss_callback(
    callback: CallbackQuery,
    state: FSMContext | None = None,
) -> None:
    if not callback.message:
        await callback.answer()
        return

    await callback.answer("Dismissed.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Dismissal flow cancelled.")
    if state:
        await state.clear()


# --- Ban FSM Flow ---


@router.message(Command("ban"))
async def cmd_ban(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()
    args = message.text.strip().split() if message.text else []
    if len(args) >= 2:
        try:
            user_id = int(args[1])
            await state.update_data(target_user_id=user_id)
            await state.set_state(BanForm.waiting_for_reason)
            await message.answer(
                f"🚫 Please enter the reason for banning user <code>{user_id}</code>:",
                parse_mode="HTML",
            )
        except ValueError:
            await message.answer("⚠️ Invalid User ID. Please provide a numeric ID.")
    else:
        await state.set_state(BanForm.waiting_for_user_id)
        await message.answer("👤 Please enter the numeric User ID you want to ban:")


@router.message(BanForm.waiting_for_user_id)
async def process_ban_user_id(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    try:
        user_id = int(text)
        await state.update_data(target_user_id=user_id)
        await state.set_state(BanForm.waiting_for_reason)
        await message.answer(
            f"🚫 Please enter the reason for banning user <code>{user_id}</code>:",
            parse_mode="HTML",
        )
    except ValueError:
        await message.answer("⚠️ Invalid User ID. Please enter a numeric ID:")


@router.message(BanForm.waiting_for_reason)
async def process_ban_reason(message: Message, state: FSMContext) -> None:
    reason = message.text.strip() if message.text else ""
    if not reason:
        await message.answer("⚠️ Reason must not be empty. Please enter the reason:")
        return

    await state.update_data(reason=reason)
    data = await state.get_data()
    user_id = data["target_user_id"]

    summary = (
        f"🚫 <b>Confirm Ban User Action</b>\n\n"
        f"👤 <b>Target User ID:</b> <code>{user_id}</code>\n"
        f"⚠️ <b>Reason:</b> {html.escape(reason)}\n"
    )
    keyboard = get_moderation_confirm_keyboard("ban", str(user_id))
    await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_ban:"))
async def handle_confirm_ban_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
    state: FSMContext | None = None,
) -> None:
    if (
        not callback.data
        or not callback.message
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    moderator_id = int(linked_user["id"])
    target_user_id = int(callback.data.split(":")[1])

    if not state:
        await callback.answer("❌ FSM state lost.", show_alert=True)
        return

    data = await state.get_data()
    if int(data.get("target_user_id", 0)) != target_user_id:
        await callback.answer("❌ User ID mismatch.", show_alert=True)
        return

    try:
        await client.ban_user_internal(
            user_id=target_user_id,
            reason=data["reason"],
            moderator_id=moderator_id,
        )
        await callback.answer("✅ User has been banned!", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"🎉 <b>Success:</b> User <code>{target_user_id}</code> has been banned.",
            parse_mode="HTML",
        )
        await state.clear()
    except Exception as e:
        await callback.message.answer(f"❌ Failed to ban user: {str(e)}")
        await callback.answer()


@router.callback_query(F.data.startswith("cancel_ban:"))
async def handle_cancel_ban_callback(
    callback: CallbackQuery,
    state: FSMContext | None = None,
) -> None:
    if not callback.message:
        await callback.answer()
        return

    await callback.answer("Cancelled.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Ban action cancelled.")
    if state:
        await state.clear()


# --- Unban FSM Flow ---


@router.message(Command("unban"))
async def cmd_unban(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()
    args = message.text.strip().split() if message.text else []
    if len(args) >= 2:
        try:
            user_id = int(args[1])
            await state.update_data(target_user_id=user_id)
            await state.set_state(UnbanForm.waiting_for_reason)
            await message.answer(
                f"🔓 Please enter the reason for unbanning user <code>{user_id}</code>:",
                parse_mode="HTML",
            )
        except ValueError:
            await message.answer("⚠️ Invalid User ID. Please provide a numeric ID.")
    else:
        await state.set_state(UnbanForm.waiting_for_user_id)
        await message.answer("👤 Please enter the numeric User ID you want to unban:")


@router.message(UnbanForm.waiting_for_user_id)
async def process_unban_user_id(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    try:
        user_id = int(text)
        await state.update_data(target_user_id=user_id)
        await state.set_state(UnbanForm.waiting_for_reason)
        await message.answer(
            f"🔓 Please enter the reason for unbanning user <code>{user_id}</code>:",
            parse_mode="HTML",
        )
    except ValueError:
        await message.answer("⚠️ Invalid User ID. Please enter a numeric ID:")


@router.message(UnbanForm.waiting_for_reason)
async def process_unban_reason(message: Message, state: FSMContext) -> None:
    reason = message.text.strip() if message.text else ""
    if not reason:
        await message.answer("⚠️ Reason must not be empty. Please enter the reason:")
        return

    await state.update_data(reason=reason)
    data = await state.get_data()
    user_id = data["target_user_id"]

    summary = (
        f"🔓 <b>Confirm Unban User Action</b>\n\n"
        f"👤 <b>Target User ID:</b> <code>{user_id}</code>\n"
        f"⚠️ <b>Reason:</b> {html.escape(reason)}\n"
    )
    keyboard = get_moderation_confirm_keyboard("unban", str(user_id))
    await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_unban:"))
async def handle_confirm_unban_callback(
    callback: CallbackQuery,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
    state: FSMContext | None = None,
) -> None:
    if (
        not callback.data
        or not callback.message
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    moderator_id = int(linked_user["id"])
    target_user_id = int(callback.data.split(":")[1])

    if not state:
        await callback.answer("❌ FSM state lost.", show_alert=True)
        return

    data = await state.get_data()
    if int(data.get("target_user_id", 0)) != target_user_id:
        await callback.answer("❌ User ID mismatch.", show_alert=True)
        return

    try:
        await client.unban_user_internal(
            user_id=target_user_id,
            reason=data["reason"],
            moderator_id=moderator_id,
        )
        await callback.answer("✅ User has been unbanned!", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"🎉 <b>Success:</b> User <code>{target_user_id}</code> has been unbanned.",
            parse_mode="HTML",
        )
        await state.clear()
    except Exception as e:
        await callback.message.answer(f"❌ Failed to unban user: {str(e)}")
        await callback.answer()


@router.callback_query(F.data.startswith("cancel_unban:"))
async def handle_cancel_unban_callback(
    callback: CallbackQuery,
    state: FSMContext | None = None,
) -> None:
    if not callback.message:
        await callback.answer()
        return

    await callback.answer("Cancelled.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Unban action cancelled.")
    if state:
        await state.clear()
