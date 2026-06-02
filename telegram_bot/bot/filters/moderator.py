from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from bot.api_client import APIClient


class ModeratorFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, client: APIClient) -> bool:
        if not event.from_user:
            return False

        user = await client.get_user_by_telegram_id(event.from_user.id)
        if not user:
            return False

        if user.get("user_role") == "moderator":
            return True

        warning_msg = "⚠️ This command is restricted to moderators only."
        if isinstance(event, Message):
            await event.answer(warning_msg)
        elif isinstance(event, CallbackQuery):
            await event.answer(text=warning_msg, show_alert=True)

        return False
