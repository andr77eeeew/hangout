from collections.abc import Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from bot.api_client import APIClient


class AuthMiddleware(BaseMiddleware):
    def __init__(self, client: APIClient | None = None) -> None:
        self.client: APIClient = client or APIClient()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, object]], Awaitable[object]],
        event: TelegramObject,
        data: dict[str, object],
    ) -> object:
        if isinstance(event, Message):
            from_user = event.from_user
            if not from_user:
                return await handler(event, data)
            text = event.text
            if text:
                cmd = text.strip().split()[0].lower()
                if cmd in ("/start", "/help", "/link"):
                    return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            from_user = event.from_user
            if not from_user:
                return await handler(event, data)
        else:
            return await handler(event, data)

        user = await self.client.get_user_by_telegram_id(from_user.id)
        if user is None:
            warning_text = (
                "Your Telegram account is not linked to Hangout yet. "
                "Please use `/link` to generate a linking code."
            )
            if isinstance(event, Message):
                await event.answer(warning_text)
            elif isinstance(event, CallbackQuery):
                await event.answer(warning_text, show_alert=True)
            return None

        data["linked_user"] = user
        return await handler(event, data)
