import asyncio
from fastapi import WebSocket
from app.schemas.chat import WebSocketEnvelope


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[int, set[WebSocket]]] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, activity_id: str, user_id: int
    ) -> None:
        async with self._lock:
            if activity_id not in self._rooms:
                self._rooms[activity_id] = {}
            if user_id not in self._rooms[activity_id]:
                self._rooms[activity_id][user_id] = set()
            self._rooms[activity_id][user_id].add(websocket)

    async def disconnect(
        self, websocket: WebSocket, activity_id: str, user_id: int
    ) -> None:
        async with self._lock:
            if activity_id in self._rooms:
                if user_id in self._rooms[activity_id]:
                    self._rooms[activity_id][user_id].discard(websocket)
                    if not self._rooms[activity_id][user_id]:
                        del self._rooms[activity_id][user_id]
                if not self._rooms[activity_id]:
                    del self._rooms[activity_id]

    async def broadcast_to_room(
        self, activity_id: str, envelope: WebSocketEnvelope
    ) -> None:
        async with self._lock:
            sockets_to_send: list[tuple[WebSocket, int]] = []
            if activity_id in self._rooms:
                for u_id, websockets in self._rooms[activity_id].items():
                    for ws in websockets:
                        sockets_to_send.append((ws, u_id))

        if not sockets_to_send:
            return

        data = envelope.model_dump_json()
        for ws, u_id in sockets_to_send:
            try:
                await ws.send_text(data)
            except Exception:
                await self.disconnect(ws, activity_id, u_id)

    async def get_room_connection_count(self, activity_id: str) -> int:
        async with self._lock:
            count = 0
            if activity_id in self._rooms:
                for websockets in self._rooms[activity_id].values():
                    count += len(websockets)
            return count

    async def get_room_user_count(self, activity_id: str) -> int:
        async with self._lock:
            if activity_id in self._rooms:
                return len(self._rooms[activity_id])
            return 0

    async def has_user_connections(self, activity_id: str, user_id: int) -> bool:
        async with self._lock:
            if activity_id in self._rooms:
                return user_id in self._rooms[activity_id]
            return False

    async def disconnect_user(
        self,
        activity_id: str,
        user_id: int,
        code: int = 4003,
        reason: str = "Kicked from activity",
    ) -> None:
        async with self._lock:
            sockets_to_close: list[WebSocket] = []
            if activity_id in self._rooms and user_id in self._rooms[activity_id]:
                sockets_to_close = list(self._rooms[activity_id][user_id])

        for ws in sockets_to_close:
            try:
                await ws.close(code=code, reason=reason)
            except Exception:
                pass
            await self.disconnect(ws, activity_id, user_id)


connection_manager = ConnectionManager()
