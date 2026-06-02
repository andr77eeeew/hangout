import html
from datetime import datetime, timezone, timedelta
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.api_client import APIClient, ValidationError
from bot.keyboards.inline import (
    get_activities_list_keyboard,
    get_activity_details_keyboard,
    get_categories_keyboard,
    get_types_keyboard,
    get_formats_keyboard,
    get_confirmation_keyboard,
)
from bot.states.activity import ActivityForm
from bot.schemas import ActivityCreatePayload
from bot.utils.formatting import format_activity_details


router = Router()


@router.message(Command("my_activities"))
async def cmd_my_activities(
    message: Message,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not linked_user or "id" not in linked_user:
        await message.answer("❌ You must link your account first using /link.")
        return

    user_id = int(linked_user["id"])
    try:
        activities = await client.get_user_created_activities(user_id)
        if not activities:
            await message.answer(
                "📂 <b>Your Created Activities</b>:\n\nYou haven't created any activities yet.",
                parse_mode="HTML",
            )
            return

        page = 1
        keyboard = get_activities_list_keyboard(
            activities=activities,
            page=page,
            page_size=5,
            callback_prefix="my_acts",
        )
        total_pages = (len(activities) + 4) // 5
        await message.answer(
            f"📂 <b>Your Created Activities</b> (Page {page}/{total_pages}):\n\n"
            "Select an activity below to view details:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception:
        await message.answer(
            "❌ Failed to retrieve your activities. Please try again later."
        )


@router.callback_query(F.data.startswith("my_acts:"))
async def handle_my_acts_callback(
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
    try:
        page = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Invalid page number.", show_alert=True)
        return

    try:
        activities = await client.get_user_created_activities(user_id)
        if not activities:
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "📂 <b>Your Created Activities</b>:\n\nYou haven't created any activities yet.",
                    parse_mode="HTML",
                )
            await callback.answer()
            return

        total_pages = (len(activities) + 4) // 5
        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        keyboard = get_activities_list_keyboard(
            activities=activities,
            page=page,
            page_size=5,
            callback_prefix="my_acts",
        )
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                f"📂 <b>Your Created Activities</b> (Page {page}/{total_pages}):\n\n"
                "Select an activity below to view details:",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        await callback.answer()
    except Exception:
        await callback.answer(
            "❌ Failed to retrieve activities. Please try again later.",
            show_alert=True,
        )


@router.message(Command("my_memberships"))
async def cmd_my_memberships(
    message: Message,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not linked_user or "id" not in linked_user:
        await message.answer("❌ You must link your account first using /link.")
        return

    user_id = int(linked_user["id"])
    try:
        activities = await client.get_user_joined_activities(user_id)
        if not activities:
            await message.answer(
                "📂 <b>Your Joined Activities</b>:\n\nYou haven't joined any activities yet.",
                parse_mode="HTML",
            )
            return

        page = 1
        keyboard = get_activities_list_keyboard(
            activities=activities,
            page=page,
            page_size=5,
            callback_prefix="my_membs",
        )
        total_pages = (len(activities) + 4) // 5
        await message.answer(
            f"📂 <b>Your Joined Activities</b> (Page {page}/{total_pages}):\n\n"
            "Select an activity below to view details:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception:
        await message.answer(
            "❌ Failed to retrieve your memberships. Please try again later."
        )


@router.callback_query(F.data.startswith("my_membs:"))
async def handle_my_membs_callback(
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
    try:
        page = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Invalid page number.", show_alert=True)
        return

    try:
        activities = await client.get_user_joined_activities(user_id)
        if not activities:
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    "📂 <b>Your Joined Activities</b>:\n\nYou haven't joined any activities yet.",
                    parse_mode="HTML",
                )
            await callback.answer()
            return

        total_pages = (len(activities) + 4) // 5
        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        keyboard = get_activities_list_keyboard(
            activities=activities,
            page=page,
            page_size=5,
            callback_prefix="my_membs",
        )
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                f"📂 <b>Your Joined Activities</b> (Page {page}/{total_pages}):\n\n"
                "Select an activity below to view details:",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        await callback.answer()
    except Exception:
        await callback.answer(
            "❌ Failed to retrieve activities. Please try again later.",
            show_alert=True,
        )


@router.message(Command("activity"))
async def cmd_activity(
    message: Message,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not linked_user or "id" not in linked_user:
        await message.answer("❌ You must link your account first using /link.")
        return

    user_id = int(linked_user["id"])
    args = message.text.strip().split() if message.text else []
    if len(args) < 2:
        await message.answer(
            "⚠️ Please provide an activity ID.\nUsage: <code>/activity &lt;activity_id&gt;</code>",
            parse_mode="HTML",
        )
        return

    activity_id = args[1]
    try:
        activity = await client.get_internal_activity(activity_id)
        text = format_activity_details(activity)
        keyboard = get_activity_details_keyboard(activity, user_id)
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception:
        await message.answer(
            "❌ Failed to retrieve activity details. Please try again later."
        )


@router.callback_query(F.data.startswith("view_act:"))
async def handle_view_act_callback(
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
    activity_id = callback.data.split(":")[1]

    try:
        activity = await client.get_internal_activity(activity_id)
        text = format_activity_details(activity)
        keyboard = get_activity_details_keyboard(activity, user_id)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        await callback.answer()
    except Exception:
        await callback.answer(
            "❌ Failed to retrieve activity details. Please try again later.",
            show_alert=True,
        )


def get_extra_data_prompt(category: str | None) -> str:
    if category == "games":
        return "🎮 Please enter the <b>Game Name</b> (e.g. Minecraft):"
    elif category == "board_games":
        return "🎲 Please enter the <b>Board Game Name</b> (e.g. Chess):"
    elif category == "movies":
        return "🎬 Please enter the <b>Movie Name</b> (e.g. Inception):"
    elif category == "anime":
        return "⛩️ Please enter the <b>Anime Name</b> (e.g. Naruto):"
    elif category == "sport":
        return "⚽ Please enter the <b>Sport Type</b> (e.g. Football):"
    elif category == "music":
        return "🎵 Please enter the <b>Music Genre</b> (e.g. Rock):"
    return "📝 Please enter details:"


@router.message(Command("cancel"))
@router.message(F.text.casefold() == "cancel")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❌ No active activity creation flow to cancel.")
        return

    await state.clear()
    await message.answer("❌ Activity creation cancelled.")


@router.callback_query(F.data == "cancel_activity_creation")
async def handle_cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await callback.answer("No active flow.", show_alert=True)
        return

    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("❌ Activity creation cancelled.")
    await callback.answer()


@router.message(Command("create_activity"))
async def cmd_create_activity(
    message: Message,
    state: FSMContext,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not linked_user or "id" not in linked_user:
        await message.answer("❌ You must link your account first using /link.")
        return

    await state.set_state(ActivityForm.waiting_for_category)
    await message.answer(
        "🎬 Let's create a new activity!\n\nSelect a category below:",
        reply_markup=get_categories_keyboard(),
    )


@router.callback_query(
    ActivityForm.waiting_for_category, F.data.startswith("category:")
)
async def handle_category_selected(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        await callback.answer()
        return

    category = callback.data.split(":")[1]
    await state.update_data(category=category)
    await state.set_state(ActivityForm.waiting_for_type)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"✅ Category set to: <b>{category.capitalize()}</b>\n\n"
            "🔓 Select the activity type (Open or Closed):",
            reply_markup=get_types_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(ActivityForm.waiting_for_type, F.data.startswith("type:"))
async def handle_type_selected(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        await callback.answer()
        return

    activity_type = callback.data.split(":")[1]
    await state.update_data(type=activity_type)
    await state.set_state(ActivityForm.waiting_for_format)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"✅ Type set to: <b>{activity_type.capitalize()}</b>\n\n"
            "🌐 Select the activity format (Online or Offline):",
            reply_markup=get_formats_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(ActivityForm.waiting_for_format, F.data.startswith("format:"))
async def handle_format_selected(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        await callback.answer()
        return

    activity_format = callback.data.split(":")[1]
    await state.update_data(format=activity_format)
    await state.set_state(ActivityForm.waiting_for_title)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"✅ Format set to: <b>{activity_format.capitalize()}</b>\n\n"
            "✏️ Please enter the activity title (3 to 100 characters):",
            parse_mode="HTML",
        )
    await callback.answer()


@router.message(ActivityForm.waiting_for_title)
async def process_title(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ Please enter a text title:")
        return

    title = message.text.strip()
    if len(title) < 3 or len(title) > 100:
        await message.answer(
            "⚠️ The title must be between 3 and 100 characters. Please try again:"
        )
        return

    await state.update_data(title=title)
    await state.set_state(ActivityForm.waiting_for_description)
    await message.answer(
        "📝 Please enter the activity description (at least 10 characters):"
    )


@router.message(ActivityForm.waiting_for_description)
async def process_description(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ Please enter a text description:")
        return

    description = message.text.strip()
    if len(description) < 10 or len(description) > 2000:
        await message.answer(
            "⚠️ The description must be between 10 and 2000 characters. Please try again:"
        )
        return

    await state.update_data(description=description)
    await state.set_state(ActivityForm.waiting_for_date)
    await message.answer(
        "📅 Please enter the activity date and time in UTC\n"
        "(format: <code>YYYY-MM-DD HH:MM</code>, e.g. <code>2026-06-02 15:30</code>):",
        parse_mode="HTML",
    )


@router.message(ActivityForm.waiting_for_date)
async def process_date(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ Please enter a valid date and time:")
        return

    text = message.text.strip()
    try:
        parsed_date = datetime.strptime(text, "%Y-%m-%d %H:%M").replace(
            tzinfo=timezone.utc
        )
        now = datetime.now(timezone.utc)
        if parsed_date < now + timedelta(hours=2):
            await message.answer(
                "⚠️ The activity date must be at least 2 hours in the future.\n"
                "Please enter a future date and time (format: <code>YYYY-MM-DD HH:MM</code>, e.g. <code>2026-06-02 18:00</code>):",
                parse_mode="HTML",
            )
            return
    except ValueError:
        await message.answer(
            "⚠️ Invalid date format. Please enter using the exact format <code>YYYY-MM-DD HH:MM</code>\n"
            "e.g. <code>2026-06-02 15:30</code>:",
            parse_mode="HTML",
        )
        return

    await state.update_data(date=parsed_date)
    data = await state.get_data()

    if data.get("format") == "offline":
        await state.set_state(ActivityForm.waiting_for_location)
        await message.answer(
            "📍 This is an offline activity. Please enter the location:"
        )
    else:
        category = data.get("category")
        if category != "foods":
            await state.set_state(ActivityForm.waiting_for_extra_data)
            prompt = get_extra_data_prompt(category)
            await message.answer(prompt, parse_mode="HTML")
        else:
            await state.set_state(ActivityForm.waiting_for_max_members)
            await message.answer(
                "👥 Please enter the maximum number of members (integer between 2 and 20):"
            )


@router.message(ActivityForm.waiting_for_location)
async def process_location(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ Please enter a text location:")
        return

    location = message.text.strip()
    await state.update_data(location=location)
    data = await state.get_data()

    category = data.get("category")
    if category != "foods":
        await state.set_state(ActivityForm.waiting_for_extra_data)
        prompt = get_extra_data_prompt(category)
        await message.answer(prompt, parse_mode="HTML")
    else:
        await state.set_state(ActivityForm.waiting_for_max_members)
        await message.answer(
            "👥 Please enter the maximum number of members (integer between 2 and 20):"
        )


@router.message(ActivityForm.waiting_for_extra_data)
async def process_extra_data(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ Please enter a valid name:")
        return

    text = message.text.strip()
    data = await state.get_data()
    category = data.get("category")

    extra_data: dict[str, str | int | bool | None] = {}
    if category == "games":
        extra_data = {
            "category": "games",
            "game_name": text,
            "platform": "cross-platform",
        }
    elif category == "board_games":
        extra_data = {
            "category": "board_games",
            "game_name": text,
        }
    elif category == "movies":
        extra_data = {
            "category": "movies",
            "movie_name": text,
        }
    elif category == "anime":
        extra_data = {
            "category": "anime",
            "anime_name": text,
        }
    elif category == "sport":
        extra_data = {
            "category": "sport",
            "sport_type": text,
        }
    elif category == "music":
        extra_data = {
            "category": "music",
            "genre": text,
        }

    await state.update_data(extra_data=extra_data)
    await state.set_state(ActivityForm.waiting_for_max_members)
    await message.answer(
        "👥 Please enter the maximum number of members (integer between 2 and 20):"
    )


@router.message(ActivityForm.waiting_for_max_members)
async def process_max_members(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ Please enter a valid number of members:")
        return

    text = message.text.strip()
    try:
        max_members = int(text)
        if not (2 <= max_members <= 20):
            raise ValueError()
    except ValueError:
        await message.answer(
            "⚠️ Maximum members must be a whole number between 2 and 20. Please try again:"
        )
        return

    await state.update_data(max_members=max_members)
    await state.set_state(ActivityForm.waiting_for_tags)
    await message.answer(
        "🏷️ Please enter tags for this activity separated by spaces (e.g. <code>gaming co-op fun</code>):",
        parse_mode="HTML",
    )


@router.message(ActivityForm.waiting_for_tags)
async def process_tags(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ Please enter at least one tag:")
        return

    text = message.text.strip()
    tags = [
        t.strip().lstrip("#").lower() for t in text.split() if t.strip().lstrip("#")
    ]
    if not tags:
        await message.answer("⚠️ At least one tag is required. Please try again:")
        return
    if len(tags) > 5:
        await message.answer("⚠️ No more than 5 tags are allowed. Please try again:")
        return

    await state.update_data(tags=tags)
    await state.set_state(ActivityForm.waiting_for_confirmation)

    data = await state.get_data()
    summary_text = (
        "<b>📝 Review your activity details:</b>\n\n"
        f"<b>Category:</b> {str(data.get('category')).capitalize()}\n"
        f"<b>Type:</b> {str(data.get('type')).capitalize()}\n"
        f"<b>Format:</b> {str(data.get('format')).capitalize()}\n"
        f"<b>Title:</b> {html.escape(str(data.get('title') or ''))}\n"
        f"<b>Description:</b> {html.escape(str(data.get('description') or ''))}\n"
        f"<b>Date (UTC):</b> {data.get('date').strftime('%Y-%m-%d %H:%M')}\n"
    )
    if data.get("location"):
        summary_text += (
            f"<b>Location:</b> {html.escape(str(data.get('location') or ''))}\n"
        )

    ed = data.get("extra_data")
    if ed:
        category = data.get("category")
        if category == "games":
            summary_text += (
                f"<b>Game Name:</b> {html.escape(str(ed.get('game_name') or ''))}\n"
            )
            summary_text += (
                f"<b>Platform:</b> {html.escape(str(ed.get('platform') or ''))}\n"
            )
        elif category == "board_games":
            summary_text += f"<b>Board Game Name:</b> {html.escape(str(ed.get('game_name') or ''))}\n"
        elif category == "movies":
            summary_text += (
                f"<b>Movie Name:</b> {html.escape(str(ed.get('movie_name') or ''))}\n"
            )
        elif category == "anime":
            summary_text += (
                f"<b>Anime Name:</b> {html.escape(str(ed.get('anime_name') or ''))}\n"
            )
        elif category == "sport":
            summary_text += (
                f"<b>Sport Type:</b> {html.escape(str(ed.get('sport_type') or ''))}\n"
            )
        elif category == "music":
            summary_text += f"<b>Genre:</b> {html.escape(str(ed.get('genre') or ''))}\n"

    summary_text += (
        f"<b>Max Members:</b> {data.get('max_members')}\n"
        f"<b>Tags:</b> {', '.join(html.escape(t) for t in (data.get('tags') or []))}\n\n"
        "Ready to create?"
    )

    await message.answer(
        summary_text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(
    ActivityForm.waiting_for_confirmation, F.data == "confirm_create"
)
async def handle_confirm_create(
    callback: CallbackQuery,
    state: FSMContext,
    client: APIClient,
    linked_user: dict[str, int | str | None] | None = None,
) -> None:
    if not linked_user or "id" not in linked_user:
        await callback.answer("❌ Account link required.", show_alert=True)
        return

    data = await state.get_data()
    user_id = int(linked_user["id"])

    try:
        payload = ActivityCreatePayload(
            title=str(data.get("title")),
            type=str(data.get("type")),
            format=str(data.get("format")),
            category=str(data.get("category")),
            description=str(data.get("description")),
            date=data.get("date"),
            max_members=int(data.get("max_members")),
            tags=list(data.get("tags") or []),
            location=data.get("location"),
            extra_data=data.get("extra_data"),
        )

        activity = await client.create_activity(user_id=user_id, payload=payload)
        await state.clear()

        formatted_details = format_activity_details(activity)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "🎉 <b>Activity successfully created!</b>\n\n" + formatted_details,
                parse_mode="HTML",
            )
        await callback.answer("Created successfully!")
    except ValidationError as e:
        await state.clear()
        if e.errors:
            error_lines = []
            for field, msg in e.errors.items():
                clean_field = field.split(".")[-1]
                error_lines.append(f"• <b>{clean_field}</b>: {html.escape(msg)}")
            error_msg = "❌ <b>Validation errors occurred:</b>\n\n" + "\n".join(
                error_lines
            )
        else:
            error_msg = f"❌ <b>Validation error:</b> {html.escape(e.message)}"

        if isinstance(callback.message, Message):
            await callback.message.edit_text(error_msg, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        await state.clear()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                f"❌ <b>Error:</b> {html.escape(str(e))}", parse_mode="HTML"
            )
        await callback.answer()
