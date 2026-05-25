from fastapi import HTTPException, status
from slugify import slugify
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tag, User, UserTag


class TagService:
    @staticmethod
    async def get_or_create_tags(db: AsyncSession, names: list[str]) -> list[Tag]:
        if not names:
            return []

        clean_names = list({n.strip().lower() for n in names})

        values = [
            {"name": name, "slug": slugify(name), "usage_count": 1}
            for name in clean_names
        ]

        stmt = insert(Tag).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={"usage_count": Tag.usage_count + 1},
        ).returning(Tag)

        result = await db.execute(stmt)
        await db.commit()

        return list(result.scalars().all())

    @staticmethod
    async def tag_toggle(tag_name: str, db: AsyncSession, current_user: User):
        slug = slugify(tag_name)

        stmt_tag = select(Tag).where(Tag.slug == slug)
        tag = (await db.execute(stmt_tag)).scalar_one_or_none()

        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag '{tag_name}' not found in global database",
            )
        stmt = select(UserTag).where(
            UserTag.user_id == current_user.id, UserTag.tag_id == tag.id
        )
        result = await db.execute(stmt)
        link = result.scalar_one_or_none()

        if link:
            await db.execute(
                delete(UserTag).where(
                    UserTag.user_id == current_user.id, UserTag.tag_id == tag.id
                )
            )
            msg = "Tag removed from favorites"
        else:
            new_link = UserTag(user_id=current_user.id, tag_id=tag.id)
            db.add(new_link)
            msg = "Tag added to favorites"

        await db.commit()

        return {
            "message": msg,
            "tag": {"id": tag.id, "name": tag.name, "slug": tag.slug},
        }
