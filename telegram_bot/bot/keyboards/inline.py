from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


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
