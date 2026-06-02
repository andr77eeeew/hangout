import html
from bot.schemas import ActivityDetails


def format_activity_details(activity: ActivityDetails) -> str:
    title = html.escape(activity.title)
    description = html.escape(activity.description)
    category = html.escape(activity.category)
    activity_format = html.escape(activity.format)

    creator_username = "Unknown"
    if activity.creator:
        creator_username = f"@{html.escape(activity.creator.username)}"

    start_str = activity.starts_at.strftime("%Y-%m-%d %H:%M")
    end_str = activity.ends_at.strftime("%Y-%m-%d %H:%M")

    max_memb = (
        str(activity.max_members) if activity.max_members is not None else "no limit"
    )
    members_str = f"{activity.current_members} / {max_memb}"

    hashtag_list = []
    for tag in activity.tags:
        clean_tag = "".join(c if c.isalnum() else "_" for c in tag).strip("_")
        if clean_tag:
            hashtag_list.append(f"#{clean_tag}")
        else:
            hashtag_list.append(f"#{html.escape(tag)}")
    tags_str = " ".join(hashtag_list) if hashtag_list else "None"

    lines = [
        f"🌟 <b>{title}</b>",
        f"📝 {description}",
        "",
        f"📅 <b>Start:</b> {start_str}",
        f"📅 <b>End:</b> {end_str}",
        f"🏷 <b>Category:</b> {category}",
        f"⚙️ <b>Format:</b> {activity_format}",
        f"👥 <b>Members:</b> {members_str}",
        f"👑 <b>Creator:</b> {creator_username}",
    ]

    if activity.location:
        lines.append(f"📍 <b>Location:</b> {html.escape(activity.location)}")
    if activity.online_link:
        link_escaped = html.escape(activity.online_link)
        if link_escaped.startswith(("http://", "https://")):
            lines.append(
                f'🌐 <b>Online Link:</b> <a href="{link_escaped}">Join Call/Meeting</a>'
            )
        else:
            lines.append(f"🌐 <b>Online Link:</b> {link_escaped}")

    lines.append(f"🏷 <b>Tags:</b> {tags_str}")

    return "\n".join(lines)
