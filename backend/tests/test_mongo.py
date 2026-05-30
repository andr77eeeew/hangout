from unittest.mock import AsyncMock, patch
from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.collection import AsyncCollection

from app.core.mongo import (
    ensure_chat_messages_indexes,
    get_chat_messages_collection,
    ensure_membership_indexes,
    ensure_game_covers_indexes,
    ensure_mongo_indexes,
    get_membership_collection,
    get_game_covers_collection,
)


async def test_get_chat_messages_collection() -> None:
    mock_db = AsyncMock()
    mock_collection = AsyncMock(spec=AsyncCollection)
    mock_db.__getitem__.return_value = mock_collection

    with patch(
        "app.core.mongo.get_mongo_db", new_callable=AsyncMock
    ) as mock_get_mongo_db:
        mock_get_mongo_db.return_value = mock_db

        collection = await get_chat_messages_collection()

        assert collection == mock_collection
        mock_get_mongo_db.assert_called_once()
        mock_db.__getitem__.assert_called_once_with("chat_messages")

        # Verify index creation is NOT called on per-request collection fetch
        mock_collection.create_index.assert_not_called()


async def test_ensure_chat_messages_indexes() -> None:
    mock_db = AsyncMock()
    mock_collection = AsyncMock(spec=AsyncCollection)
    mock_db.__getitem__.return_value = mock_collection

    with patch(
        "app.core.mongo.get_mongo_db", new_callable=AsyncMock
    ) as mock_get_mongo_db:
        mock_get_mongo_db.return_value = mock_db

        await ensure_chat_messages_indexes()

        mock_get_mongo_db.assert_called_once()
        mock_db.__getitem__.assert_called_once_with("chat_messages")

        assert mock_collection.create_index.call_count == 2
        calls = mock_collection.create_index.call_args_list
        assert calls[0][0][0] == [("activity_id", ASCENDING), ("_id", DESCENDING)]
        assert calls[1][0][0] == [("activity_id", ASCENDING)]


async def test_get_membership_collection_no_index() -> None:
    mock_db = AsyncMock()
    mock_collection = AsyncMock(spec=AsyncCollection)
    mock_db.__getitem__.return_value = mock_collection

    with patch("app.core.mongo.get_mongo_db", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_db
        col = await get_membership_collection()
        assert col == mock_collection
        mock_collection.create_index.assert_not_called()


async def test_get_game_covers_collection_no_index() -> None:
    mock_db = AsyncMock()
    mock_collection = AsyncMock(spec=AsyncCollection)
    mock_db.__getitem__.return_value = mock_collection

    with patch("app.core.mongo.get_mongo_db", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_db
        col = await get_game_covers_collection()
        assert col == mock_collection
        mock_collection.create_index.assert_not_called()


async def test_ensure_membership_indexes() -> None:
    mock_db = AsyncMock()
    mock_collection = AsyncMock(spec=AsyncCollection)
    mock_db.__getitem__.return_value = mock_collection

    with patch("app.core.mongo.get_mongo_db", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_db
        await ensure_membership_indexes()
        assert mock_collection.create_index.call_count == 3


async def test_ensure_game_covers_indexes() -> None:
    mock_db = AsyncMock()
    mock_collection = AsyncMock(spec=AsyncCollection)
    mock_db.__getitem__.return_value = mock_collection

    with patch("app.core.mongo.get_mongo_db", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_db
        await ensure_game_covers_indexes()
        assert mock_collection.create_index.call_count == 1
        calls = mock_collection.create_index.call_args_list
        assert calls[0][0][0] == [("game_id", ASCENDING)]
        assert calls[0][1] == {"unique": True}


async def test_ensure_mongo_indexes() -> None:
    with (
        patch(
            "app.core.mongo.ensure_chat_messages_indexes", new_callable=AsyncMock
        ) as m_chat,
        patch(
            "app.core.mongo.ensure_membership_indexes", new_callable=AsyncMock
        ) as m_mem,
        patch(
            "app.core.mongo.ensure_game_covers_indexes", new_callable=AsyncMock
        ) as m_game,
    ):
        await ensure_mongo_indexes()
        m_chat.assert_called_once()
        m_mem.assert_called_once()
        m_game.assert_called_once()
