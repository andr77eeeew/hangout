from unittest.mock import AsyncMock, patch
from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.collection import AsyncCollection

from app.core.mongo import ensure_chat_messages_indexes, get_chat_messages_collection


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
