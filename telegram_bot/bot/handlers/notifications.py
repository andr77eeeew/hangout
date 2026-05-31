from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from bot.api_client import APIClient
from bot.keyboards import get_notifications_keyboard

router = Router()


@router.message(Command("notifications"))
async def cmd_notifications(message: Message, client: APIClient) -> None:
    if not message.from_user:
        return

    try:
        prefs = await client.get_notification_preferences(message.from_user.id)
        keyboard = get_notifications_keyboard(prefs)
        await message.answer(
            "🔔 <b>Notification Preferences</b>\n\n"
            "Configure which updates you want to receive on Telegram. Tap any button to toggle:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception:
        await message.answer(
            "❌ Failed to load notification preferences. Please try again later."
        )


@router.callback_query(F.data.startswith("toggle:"))
async def handle_toggle_callback(callback: CallbackQuery, client: APIClient) -> None:
    if not callback.from_user or not callback.data:
        await callback.answer()
        return

    field_name = callback.data.split(":")[1]

    try:
        prefs = await client.get_notification_preferences(callback.from_user.id)
        current_state = prefs.get(field_name, False)
        new_state = not bool(current_state)

        updated_prefs = await client.update_notification_preferences(
            callback.from_user.id, {field_name: new_state}
        )

        keyboard = get_notifications_keyboard(updated_prefs)

        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer("Preference updated!")
    except Exception:
        await callback.answer(
            "❌ Failed to update preference. Please try again.", show_alert=True
        )
