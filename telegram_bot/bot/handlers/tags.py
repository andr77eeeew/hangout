import html
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from bot.api_client import APIClient
from bot.keyboards.inline import get_favorite_tags_keyboard

router = Router()


@router.message(Command("my_tags"))
async def cmd_my_tags(
    message: Message,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not linked_user or "id" not in linked_user:
        await message.answer("❌ You must link your account first using /link.")
        return

    user_id = int(linked_user["id"])
    try:
        tags = await client.get_favorite_tags(user_id)
        if not tags:
            await message.answer(
                "⭐ You don't have any favorite tags yet.\n"
                "Use <code>/add_tag &lt;tag_name&gt;</code> to add one!",
                parse_mode="HTML",
            )
            return

        keyboard = get_favorite_tags_keyboard(tags)
        await message.answer(
            "⭐ <b>Your Favorite Tags</b>\n\n"
            "Here are your favorite tags. Click the cross emoji next to a tag to remove it:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Failed to fetch favorite tags: {str(e)}")


@router.message(Command("add_tag"))
async def cmd_add_tag(
    message: Message,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not linked_user or "id" not in linked_user:
        await message.answer("❌ You must link your account first using /link.")
        return

    user_id = int(linked_user["id"])
    if not message.text:
        await message.answer(
            "⚠️ Please provide a tag name.\nUsage: <code>/add_tag &lt;tag_name&gt;</code>",
            parse_mode="HTML",
        )
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "⚠️ Please provide a tag name.\nUsage: <code>/add_tag &lt;tag_name&gt;</code>",
            parse_mode="HTML",
        )
        return

    tag_name = parts[1].strip()
    try:
        await client.add_favorite_tag(user_id, tag_name)
        await message.answer(
            f"✅ Tag <b>{html.escape(tag_name)}</b> successfully added to your favorites!",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Failed to add tag: {str(e)}")


@router.message(Command("remove_tag"))
async def cmd_remove_tag(
    message: Message,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not linked_user or "id" not in linked_user:
        await message.answer("❌ You must link your account first using /link.")
        return

    user_id = int(linked_user["id"])
    if not message.text:
        await message.answer(
            "⚠️ Please provide a tag name.\nUsage: <code>/remove_tag &lt;tag_name&gt;</code>",
            parse_mode="HTML",
        )
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "⚠️ Please provide a tag name.\nUsage: <code>/remove_tag &lt;tag_name&gt;</code>",
            parse_mode="HTML",
        )
        return

    tag_name = parts[1].strip()
    try:
        await client.remove_favorite_tag(user_id, tag_name)
        await message.answer(
            f"✅ Tag <b>{html.escape(tag_name)}</b> successfully removed from your favorites!",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Failed to remove tag: {str(e)}")


@router.callback_query(F.data.startswith("remove_tag:"))
async def handle_remove_tag_callback(
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
    tag_name = callback.data.split(":", 1)[1]

    try:
        await client.remove_favorite_tag(user_id, tag_name)
        tags = await client.get_favorite_tags(user_id)

        if not tags:
            if isinstance(callback.message, Message):
                await callback.message.delete()
            await callback.answer(f"Removed tag: {tag_name}. No favorite tags left.")
        else:
            keyboard = get_favorite_tags_keyboard(tags)
            if isinstance(callback.message, Message):
                await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer(f"Removed tag: {tag_name}")
    except Exception as e:
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)
