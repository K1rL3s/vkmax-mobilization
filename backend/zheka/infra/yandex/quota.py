from collections import defaultdict, deque
from time import monotonic

from zheka.core.ids import UserId

QUOTA_CALLS = 60
QUOTA_WINDOW_SECONDS = 3600.0


class YandexQuota:
    __slots__ = ("_calls",)

    def __init__(self) -> None:
        self._calls: defaultdict[UserId, deque[float]] = defaultdict(deque)

    def take(self, user_id: UserId) -> bool:
        now = monotonic()
        calls = self._calls[user_id]
        while calls and calls[0] <= now - QUOTA_WINDOW_SECONDS:
            calls.popleft()
        if len(calls) >= QUOTA_CALLS:
            return False
        calls.append(now)
        return True
