import asyncio
import time
from collections import deque
from types import TracebackType
from typing import Self


class RateLimiter:
    __slots__ = ("_calls", "_lock", "max_calls", "period")

    def __init__(self, max_calls: int, period: float = 1.0) -> None:
        self.max_calls = max_calls
        self.period = period
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.period:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return self
                sleep_for = self._calls[0] + self.period - now
            await asyncio.sleep(sleep_for)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass
