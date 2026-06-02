from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.api_client import APIClient

router = Router()


@router.message(Command("link"))
async def cmd_link(message: Message, client: APIClient) -> None:
    if not message.from_user:
        return

    try:
        code = await client.generate_link_code(message.from_user.id)
        response_text = (
            "🔑 Here is your Hangout link code:\n\n"
            f"<code>{code}</code>\n\n"
            "Tap the code to copy it, then paste it in your Hangout account settings to link your Telegram profile."
        )
        await message.answer(response_text, parse_mode="HTML")
    except Exception:
        await message.answer(
            "❌ Failed to generate a linking code. Please try again later."
        )


@router.message(Command("status"))
async def cmd_status(
    message: Message, linked_user: dict[str, int | str | None] | None = None
) -> None:
    if not linked_user:
        await message.answer(
            "Your Telegram account is not linked to Hangout yet. Please use /link to generate a linking code."
        )
        return

    username = linked_user.get("username") or "Unknown"
    status_text = (
        "✅ <b>Connection Status</b>:\n\n"
        f"Your Telegram account is successfully linked to Hangout username: <b>{username}</b>."
    )
    await message.answer(status_text, parse_mode="HTML")


@router.message(Command("unlink"))
async def cmd_unlink(message: Message, client: APIClient) -> None:
    if not message.from_user:
        return

    try:
        await client.unlink(message.from_user.id)
        await message.answer(
            "🔌 <b>Account Unlinked</b>\n\n"
            "Your Telegram account has been successfully unlinked from Hangout. "
            "You will no longer receive any notifications.",
            parse_mode="HTML",
        )
    except Exception:
        await message.answer("❌ Failed to unlink account. Please try again later.")
