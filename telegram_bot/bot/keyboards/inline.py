from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.schemas import ActivitySummary, ActivityDetails, TagSummary, ReportDetails


def get_notifications_keyboard(
    preferences: dict[str, int | bool],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    membership_label = (
        "✅ Membership Updates"
        if preferences.get("membership_updates")
        else "❌ Membership Updates"
    )
    activity_label = (
        "✅ Activity Reminders"
        if preferences.get("activity_reminders")
        else "❌ Activity Reminders"
    )
    tag_label = (
        "✅ Tag Subscriptions"
        if preferences.get("tag_subscriptions")
        else "❌ Tag Subscriptions"
    )

    builder.button(text=membership_label, callback_data="toggle:membership_updates")
    builder.button(text=activity_label, callback_data="toggle:activity_reminders")
    builder.button(text=tag_label, callback_data="toggle:tag_subscriptions")

    builder.adjust(1)
    return builder.as_markup()


def get_activities_list_keyboard(
    activities: list[ActivitySummary],
    page: int,
    page_size: int = 5,
    callback_prefix: str = "my_acts",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    total_pages = (len(activities) + page_size - 1) // page_size

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_activities = activities[start_idx:end_idx]

    for activity in page_activities:
        builder.button(text=activity.title, callback_data=f"view_act:{activity.id}")
    builder.adjust(1)

    nav_buttons: list[InlineKeyboardButton] = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Back", callback_data=f"{callback_prefix}:{page - 1}"
            )
        )
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Next ➡️", callback_data=f"{callback_prefix}:{page + 1}"
            )
        )

    if nav_buttons:
        builder.row(*nav_buttons)

    return builder.as_markup()


def get_activity_details_keyboard(
    activity: ActivityDetails,
    user_id: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if activity.creator_id == user_id:
        builder.button(
            text="👥 Pending Members",
            callback_data=f"pending_members:{activity.id}",
        )
    else:
        builder.button(
            text="➕ Join Activity",
            callback_data=f"join_act:{activity.id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def get_categories_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎮 Games", callback_data="category:games")
    builder.button(text="🎲 Board Games", callback_data="category:board_games")
    builder.button(text="🎬 Movies", callback_data="category:movies")
    builder.button(text="🍲 Foods", callback_data="category:foods")
    builder.button(text="🎵 Music", callback_data="category:music")
    builder.button(text="⛩️ Anime", callback_data="category:anime")
    builder.button(text="⚽ Sport", callback_data="category:sport")
    builder.button(text="❌ Cancel", callback_data="cancel_activity_creation")
    builder.adjust(2)
    return builder.as_markup()


def get_types_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔓 Open", callback_data="type:open")
    builder.button(text="🔒 Closed", callback_data="type:closed")
    builder.button(text="❌ Cancel", callback_data="cancel_activity_creation")
    builder.adjust(2)
    return builder.as_markup()


def get_formats_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🌐 Online", callback_data="format:online")
    builder.button(text="📍 Offline", callback_data="format:offline")
    builder.button(text="❌ Cancel", callback_data="cancel_activity_creation")
    builder.adjust(2)
    return builder.as_markup()


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirm & Create", callback_data="confirm_create")
    builder.button(text="❌ Cancel", callback_data="cancel_activity_creation")
    builder.adjust(2)
    return builder.as_markup()


def get_membership_action_keyboard(membership_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve", callback_data=f"approve:{membership_id}")
    builder.button(text="❌ Reject", callback_data=f"reject:{membership_id}")
    builder.adjust(2)
    return builder.as_markup()


def get_kick_confirmation_keyboard(membership_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚠️ Confirm Kick", callback_data=f"confirm_kick:{membership_id}")
    builder.button(text="❌ Cancel", callback_data=f"cancel_kick:{membership_id}")
    builder.adjust(2)
    return builder.as_markup()


def get_favorite_tags_keyboard(tags: list[TagSummary]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tag in tags:
        builder.button(text=f"❌ {tag.name}", callback_data=f"remove_tag:{tag.name}")
    builder.adjust(1)
    return builder.as_markup()


def get_reports_list_keyboard(
    reports: list[ReportDetails],
    page: int,
    has_more: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for report in reports:
        builder.button(
            text=f"Report #{report.id[:8]} - {report.reason[:20]}",
            callback_data=f"view_report:{report.id}",
        )
    builder.adjust(1)

    nav_buttons: list[InlineKeyboardButton] = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"reports_page:{page - 1}",
            )
        )
    if has_more:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Next ➡️",
                callback_data=f"reports_page:{page + 1}",
            )
        )
    if nav_buttons:
        builder.row(*nav_buttons)

    return builder.as_markup()


def get_report_details_keyboard(
    report: ReportDetails,
    moderator_id: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if report.status == "open":
        builder.button(
            text="📥 Take Report",
            callback_data=f"take_report:{report.id}",
        )
    elif report.status == "under_review":
        if moderator_id is None or report.moderator_id == moderator_id:
            builder.button(
                text="✅ Resolve Report",
                callback_data=f"resolve_report:{report.id}",
            )
            builder.button(
                text="❌ Dismiss Report",
                callback_data=f"dismiss_report:{report.id}",
            )
    builder.adjust(1)
    return builder.as_markup()


def get_ban_decision_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Yes, ban user", callback_data="ban:yes")
    builder.button(text="No, just resolve", callback_data="ban:no")
    builder.adjust(2)
    return builder.as_markup()


def get_moderation_confirm_keyboard(
    action: str,
    target_id: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Confirm",
        callback_data=f"confirm_{action}:{target_id}",
    )
    builder.button(
        text="❌ Cancel",
        callback_data=f"cancel_{action}:{target_id}",
    )
    builder.adjust(2)
    return builder.as_markup()
