"""Tests for activity feed filters (Task 11).

Tests are at the service level — we call ActivityService.list_feed directly
with mocked AsyncCollection and AsyncSession.  This lets us verify
the MongoDB query dict that is built for each filter combination
without wiring up the full HTTP → router → response-validation chain.
"""

from datetime import datetime, timezone
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.schemas.activity import ActivityCategory, ActivityFormat
from app.services.activity import ActivityService


# ── Helpers ──────────────────────────────────────────────────────────────────

VALID_OID = str(ObjectId())


def _activity_doc(
    *,
    title: str = "Test Activity",
    category: str = "games",
    fmt: str = "online",
    tags: list[str] | None = None,
    date: str = "2026-10-10T12:00:00Z",
    extra_data: dict | None = None,
):
    """Build a minimal activity document that satisfies ActivityResponse."""
    return {
        "_id": ObjectId(),
        "title": title,
        "description": "Long enough description for the schema validation here",
        "type": "open",
        "format": fmt,
        "category": category,
        "date": date,
        "max_members": 10,
        "creator_id": 1,
        "status": "active",
        "tags": tags or ["tag1"],
        "created_at": "2026-04-01T12:00:00Z",
        "updated_at": "2026-04-01T12:00:00Z",
        "current_members": 1,
        "extra_data": extra_data
        or {"category": category, "game_name": "MC", "platform": "pc"},
    }


def _mock_collection(docs: list[dict]):
    """Create a mock AsyncCollection whose find().sort().limit().to_list() returns docs."""
    col = AsyncMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=docs
    )
    col.find = MagicMock(return_value=mock_cursor)
    return col


def _mock_db():
    """Create a mock AsyncSession — we patch _fetch_users_map so db is unused."""
    return AsyncMock()


def _mock_s3():
    mock = MagicMock()
    mock.generate_presigned_url.return_value = "http://s3/img.jpg"
    return mock


async def _call_feed(
    col,
    *,
    category=None,
    fmt=None,
    tags=None,
    date_from=None,
    date_to=None,
    cursor=None,
    limit=10,
):
    """Shortcut to call list_feed with patched _fetch_users_map."""
    db = _mock_db()
    s3 = _mock_s3()

    # Patch _fetch_users_map to avoid real SQL queries
    original = ActivityService._fetch_users_map
    ActivityService._fetch_users_map = AsyncMock(return_value={})  # type: ignore[method-assign]
    try:
        result = await ActivityService.list_feed(
            collection=col,
            db=db,
            s3_public_sign=s3,
            limit=limit,
            cursor=cursor,
            category=category,
            format=fmt,
            tags=tags,
            date_from=date_from,
            date_to=date_to,
        )
    finally:
        ActivityService._fetch_users_map = original  # type: ignore[method-assign]

    return result, col


def _get_query(col) -> dict:
    """Extract the MongoDB query dict passed to collection.find()."""
    return col.find.call_args[0][0]


# ═════════════════════════════════════════════════════════════════════════════
# FILTER TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestFeedFilterByCategory:
    async def test_filter_by_category(self):
        doc = _activity_doc(
            category="sport", extra_data={"category": "sport", "sport_type": "football"}
        )
        col = _mock_collection([doc])

        result, col = await _call_feed(col, category=ActivityCategory.sport)

        query = _get_query(col)
        assert query["category"] == "sport"
        assert query["status"] == "active"

    async def test_no_category_filter(self):
        col = _mock_collection([_activity_doc()])

        result, col = await _call_feed(col)

        query = _get_query(col)
        assert "category" not in query
        assert query["status"] == "active"


class TestFeedFilterByFormat:
    async def test_filter_by_format_online(self):
        col = _mock_collection([_activity_doc(fmt="online")])

        result, col = await _call_feed(col, fmt=ActivityFormat.online)

        query = _get_query(col)
        assert query["format"] == "online"

    async def test_filter_by_format_offline(self):
        col = _mock_collection([])

        result, col = await _call_feed(col, fmt=ActivityFormat.offline)

        query = _get_query(col)
        assert query["format"] == "offline"


class TestFeedFilterByTags:
    async def test_filter_by_single_tag(self):
        col = _mock_collection([_activity_doc(tags=["minecraft"])])

        result, col = await _call_feed(col, tags=["minecraft"])

        query = _get_query(col)
        assert query["tags"] == {"$all": ["minecraft"]}

    async def test_filter_by_multiple_tags_and_logic(self):
        col = _mock_collection([_activity_doc(tags=["minecraft", "survival"])])

        result, col = await _call_feed(col, tags=["minecraft", "survival"])

        query = _get_query(col)
        assert query["tags"] == {"$all": ["minecraft", "survival"]}

    async def test_no_tags_filter(self):
        col = _mock_collection([_activity_doc()])

        result, col = await _call_feed(col)

        query = _get_query(col)
        assert "tags" not in query


class TestFeedFilterByDate:
    async def test_filter_by_date_from(self):
        dt = datetime(2026, 6, 1, tzinfo=timezone.utc)
        col = _mock_collection([])

        result, col = await _call_feed(col, date_from=dt)

        query = _get_query(col)
        assert query["date"]["$gte"] == dt
        assert "$lte" not in query["date"]

    async def test_filter_by_date_to(self):
        dt = datetime(2026, 12, 31, tzinfo=timezone.utc)
        col = _mock_collection([])

        result, col = await _call_feed(col, date_to=dt)

        query = _get_query(col)
        assert query["date"]["$lte"] == dt
        assert "$gte" not in query["date"]

    async def test_filter_by_date_range(self):
        dt_from = datetime(2026, 6, 1, tzinfo=timezone.utc)
        dt_to = datetime(2026, 12, 31, tzinfo=timezone.utc)
        col = _mock_collection([])

        result, col = await _call_feed(col, date_from=dt_from, date_to=dt_to)

        query = _get_query(col)
        assert query["date"]["$gte"] == dt_from
        assert query["date"]["$lte"] == dt_to

    async def test_no_date_filter(self):
        col = _mock_collection([_activity_doc()])

        result, col = await _call_feed(col)

        query = _get_query(col)
        assert "date" not in query


class TestFeedCombinedFilters:
    async def test_category_and_format(self):
        col = _mock_collection([])

        result, col = await _call_feed(
            col, category=ActivityCategory.games, fmt=ActivityFormat.online
        )

        query = _get_query(col)
        assert query["status"] == "active"
        assert query["category"] == "games"
        assert query["format"] == "online"

    async def test_all_filters_combined(self):
        dt_from = datetime(2026, 6, 1, tzinfo=timezone.utc)
        dt_to = datetime(2026, 12, 31, tzinfo=timezone.utc)
        col = _mock_collection([])

        result, col = await _call_feed(
            col,
            category=ActivityCategory.sport,
            fmt=ActivityFormat.offline,
            tags=["football", "friendly"],
            date_from=dt_from,
            date_to=dt_to,
        )

        query = _get_query(col)
        assert query["status"] == "active"
        assert query["category"] == "sport"
        assert query["format"] == "offline"
        assert query["tags"] == {"$all": ["football", "friendly"]}
        assert query["date"]["$gte"] == dt_from
        assert query["date"]["$lte"] == dt_to


class TestFeedCursorWithFilters:
    async def test_cursor_adds_id_filter(self):
        oid = str(ObjectId())
        col = _mock_collection([])

        result, col = await _call_feed(col, cursor=oid)

        query = _get_query(col)
        assert query["_id"] == {"$lt": ObjectId(oid)}

    async def test_cursor_with_category_filter(self):
        oid = str(ObjectId())
        col = _mock_collection([])

        result, col = await _call_feed(col, cursor=oid, category=ActivityCategory.anime)

        query = _get_query(col)
        assert query["_id"] == {"$lt": ObjectId(oid)}
        assert query["category"] == "anime"
        assert query["status"] == "active"

    async def test_invalid_cursor_raises_400(self):
        col = _mock_collection([])

        with pytest.raises(HTTPException) as exc_info:
            await _call_feed(col, cursor="not-an-objectid")

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid cursor"


class TestFeedNoFilters:
    async def test_default_query_only_active(self):
        """Without any filters, only status=active should be in the query."""
        doc = _activity_doc()
        col = _mock_collection([doc])

        result, col = await _call_feed(col)

        query = _get_query(col)
        assert query == {"status": "active"}

    async def test_returns_items_and_pagination(self):
        doc = _activity_doc()
        col = _mock_collection([doc])

        result, _ = await _call_feed(col, limit=10)

        assert len(result.items) == 1
        assert result.has_more is False
        assert result.next_cursor is None

    async def test_has_more_when_extra_docs(self):
        """When limit+1 docs returned, has_more=True and next_cursor is set."""
        docs = [_activity_doc() for _ in range(3)]
        col = _mock_collection(docs)

        result, _ = await _call_feed(col, limit=2)

        assert result.has_more is True
        assert len(result.items) == 2
        assert result.next_cursor is not None

    async def test_empty_feed(self):
        col = _mock_collection([])

        result, _ = await _call_feed(col)

        assert len(result.items) == 0
        assert result.has_more is False
        assert result.next_cursor is None
