import time


MAX_MESSAGES_PER_WINDOW = 5
WINDOW_SECONDS = 10
MAX_VIOLATIONS_BEFORE_DISCONNECT = 3


class ChatRateLimiter:
    def __init__(self) -> None:
        self._timestamps: dict[tuple[str, int], list[float]] = {}
        self._violations: dict[tuple[str, int], int] = {}

    def check_rate_limit(self, activity_id: str, user_id: int) -> bool:
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

    def get_violation_count(self, activity_id: str, user_id: int) -> int:
        return self._violations.get((activity_id, user_id), 0)

    def cleanup_user(self, activity_id: str, user_id: int) -> None:
        key = (activity_id, user_id)
        self._timestamps.pop(key, None)
        self._violations.pop(key, None)


chat_rate_limiter = ChatRateLimiter()
