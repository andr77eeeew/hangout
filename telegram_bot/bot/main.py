import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from bot.api_client import APIClient
from bot.config import settings
from bot.handlers import get_handlers_router
from bot.middlewares import AuthMiddleware

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("telegram_bot")


async def main() -> None:
    token = settings.TELEGRAM_BOT_TOKEN.get_secret_value()
    if not token or token == "dummy_bot_token" or token.strip() == "":
        logger.warning(
            "TELEGRAM_BOT_TOKEN is not configured or is empty. "
            "Telegram bot service will stop gracefully."
        )
        return

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    client = APIClient()
    dp["client"] = client

    auth_middleware = AuthMiddleware(client)
    dp.message.middleware(auth_middleware)
    dp.callback_query.middleware(auth_middleware)

    dp.include_router(get_handlers_router())

    logger.info("Starting Telegram Bot MVP...")
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Shutting down Telegram Bot MVP...")
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
