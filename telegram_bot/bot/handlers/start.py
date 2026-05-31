from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    welcome_text = (
        "👋 Welcome to the <b>Hangout Bot</b>!\n\n"
        "Here you can manage your notification preferences and keep track of your local activities.\n\n"
        "🔗 <b>Linking your account</b>:\n"
        "1. Open the Hangout web/app interface\n"
        "2. Navigate to your Account Settings -> Telegram Settings\n"
        "3. Generate a 6-digit code using the /link command\n"
        "4. Enter this code in the Hangout interface to complete the connection.\n\n"
        "Use /help to see all available commands."
    )
    await message.answer(welcome_text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    help_text = (
        "🤖 <b>Hangout Bot Commands</b>:\n\n"
        "📥 <b>Public Commands:</b>\n"
        "/start - Start the bot and get welcome info\n"
        "/help - Show this help message with command list\n"
        "/link - Generate a 6-digit verification code to link your Hangout account\n\n"
        "🔐 <b>Linked-only Commands:</b>\n"
        "/status - View your connection status and Hangout username\n"
        "/notifications - View and manage your notification preferences\n"
        "/unlink - Unlink your Telegram account from Hangout"
    )
    await message.answer(help_text, parse_mode="HTML")
