import asyncio
import time
from collections import deque
from types import TracebackType
from typing import Self


class RateLimiter:
    # не больше max_calls вызовов за скользящую секунду
    __slots__ = ("_calls", "_lock", "max_calls")

    def __init__(self, max_calls: int) -> None:
        self.max_calls = max_calls
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= 1:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return self
                sleep_for = self._calls[0] + 1 - now
            await asyncio.sleep(sleep_for)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass
