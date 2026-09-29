from collections import defaultdict, deque
from time import monotonic
from typing import ClassVar

from zheka.core.ids import UserId

UPLOAD_CALLS = 30


class Quota:
    __slots__ = ("_calls",)

    calls: ClassVar[int]
    window_seconds: ClassVar[float] = 3600.0

    def __init__(self) -> None:
        self._calls: defaultdict[UserId, deque[float]] = defaultdict(deque)

    def take(self, user_id: UserId) -> bool:
        now = monotonic()
        calls = self._calls[user_id]
        while calls and calls[0] <= now - self.window_seconds:
            calls.popleft()
        if len(calls) >= self.calls:
            return False
        calls.append(now)
        return True


class UploadQuota(Quota):
    __slots__ = ()

    calls = UPLOAD_CALLS


HOUSE_ADD_CALLS = 5


class HouseAddQuota(Quota):
    __slots__ = ()

    calls = HOUSE_ADD_CALLS


HOUSE_LOOKUP_CALLS = 60


class HouseLookupQuota(Quota):
    __slots__ = ()

    calls = HOUSE_LOOKUP_CALLS


VERIFY_CALLS = 10


class VerifyQuota(Quota):
    __slots__ = ()

    calls = VERIFY_CALLS
