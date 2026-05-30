from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tag, User, UserTag
from app.services.tag import TagService


async def test_get_or_create_tags_empty() -> None:
    db = AsyncMock(spec=AsyncSession)
    result = await TagService.get_or_create_tags(db, [])
    assert result == []
    db.execute.assert_not_called()


async def test_get_or_create_tags_success() -> None:
    db = AsyncMock(spec=AsyncSession)

    # Mock the return values from PostgreSQL returning statement
    mock_tags = [
        Tag(id=1, name="python", slug="python", usage_count=1),
        Tag(id=2, name="async", slug="async", usage_count=2),
    ]
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = mock_tags
    db.execute.return_value = mock_execute_result

    result = await TagService.get_or_create_tags(db, ["  Python ", "async", "python"])

    # Verify input deduplication, lowercasing, and stripping
    assert len(result) == 2
    assert result[0].name == "python"
    assert result[1].name == "async"

    db.execute.assert_called_once()
    db.commit.assert_called_once()


async def test_tag_toggle_not_found() -> None:
    db = AsyncMock(spec=AsyncSession)
    current_user = User(id=42, username="testuser")

    # Mock db.execute to return None for the Tag select query
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_execute_result

    with pytest.raises(HTTPException) as exc_info:
        await TagService.tag_toggle("missing-tag", db, current_user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "Tag 'missing-tag' not found in global database" in exc_info.value.detail
    db.commit.assert_not_called()


async def test_tag_toggle_add_to_favorites() -> None:
    db = AsyncMock(spec=AsyncSession)
    current_user = User(id=42, username="testuser")
    mock_tag = Tag(id=10, name="gaming", slug="gaming")

    # Mock 1st query (select Tag) -> returns mock_tag
    # Mock 2nd query (select UserTag link) -> returns None (not currently in favorites)
    mock_execute_result_tag = MagicMock()
    mock_execute_result_tag.scalar_one_or_none.return_value = mock_tag

    mock_execute_result_link = MagicMock()
    mock_execute_result_link.scalar_one_or_none.return_value = None

    db.execute.side_effect = [mock_execute_result_tag, mock_execute_result_link]

    res = await TagService.tag_toggle("gaming", db, current_user)

    assert res["message"] == "Tag added to favorites"
    assert res["tag"]["id"] == 10
    assert res["tag"]["name"] == "gaming"

    # Verify a new UserTag ORM object was added to the session
    db.add.assert_called_once()
    added_obj = db.add.call_args[0][0]
    assert isinstance(added_obj, UserTag)
    assert added_obj.user_id == 42
    assert added_obj.tag_id == 10
    db.commit.assert_called_once()


async def test_tag_toggle_remove_from_favorites() -> None:
    db = AsyncMock(spec=AsyncSession)
    current_user = User(id=42, username="testuser")
    mock_tag = Tag(id=10, name="gaming", slug="gaming")
    mock_link = UserTag(user_id=42, tag_id=10)

    # Mock 1st query (select Tag) -> returns mock_tag
    # Mock 2nd query (select UserTag link) -> returns mock_link (already in favorites)
    mock_execute_result_tag = MagicMock()
    mock_execute_result_tag.scalar_one_or_none.return_value = mock_tag

    mock_execute_result_link = MagicMock()
    mock_execute_result_link.scalar_one_or_none.return_value = mock_link

    mock_execute_result_delete = MagicMock()

    db.execute.side_effect = [
        mock_execute_result_tag,
        mock_execute_result_link,
        mock_execute_result_delete,
    ]

    res = await TagService.tag_toggle("gaming", db, current_user)

    assert res["message"] == "Tag removed from favorites"
    assert res["tag"]["id"] == 10

    # Verify delete query was executed
    assert db.execute.call_count == 3
    db.commit.assert_called_once()
