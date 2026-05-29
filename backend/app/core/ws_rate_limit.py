import asyncio
import time


MAX_MESSAGES_PER_WINDOW = 5
WINDOW_SECONDS = 10
MAX_VIOLATIONS_BEFORE_DISCONNECT = 3


class ChatRateLimiter:
    def __init__(self) -> None:
        self._timestamps: dict[tuple[str, int], list[float]] = {}
        self._violations: dict[tuple[str, int], int] = {}
        self._locks: dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}

    @property
    def _lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.Lock()
        if loop not in self._locks:
            self._locks[loop] = asyncio.Lock()
        return self._locks[loop]

    async def check_rate_limit(self, activity_id: str, user_id: int) -> bool:
        async with self._lock:
            key = (activity_id, user_id)
            now = time.monotonic()
            cutoff = now - WINDOW_SECONDS

            timestamps = self._timestamps.get(key, [])
            timestamps = [ts for ts in timestamps if ts > cutoff]

            if len(timestamps) >= MAX_MESSAGES_PER_WINDOW:
                self._timestamps[key] = timestamps
                self._violations[key] = self._violations.get(key, 0) + 1
                return False

            timestamps.append(now)
            self._timestamps[key] = timestamps
            self._violations[key] = 0
            return True

    async def get_violation_count(self, activity_id: str, user_id: int) -> int:
        async with self._lock:
            return self._violations.get((activity_id, user_id), 0)

    async def cleanup_user(self, activity_id: str, user_id: int) -> None:
        async with self._lock:
            key = (activity_id, user_id)
            self._timestamps.pop(key, None)
            self._violations.pop(key, None)


chat_rate_limiter = ChatRateLimiter()
