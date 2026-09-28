import logging
from typing import Any

from taskiq import AsyncBroker
from taskiq.kicker import AsyncKicker

from zheka.broker.task_names import TaskName

logger = logging.getLogger(__name__)

RENDERED_FROM_DB = frozenset({TaskName.SYNC_CHAT_CARD})


class TaskPublisher:
    __slots__ = ("_broker", "_pending")

    def __init__(self, broker: AsyncBroker) -> None:
        self._broker = broker
        self._pending: list[tuple[TaskName, dict[str, Any]]] = []

    def publish(self, name: TaskName, **kwargs: Any) -> None:
        if name in RENDERED_FROM_DB and (name, kwargs) in self._pending:
            return
        self._pending.append((name, kwargs))

    async def flush(self) -> None:
        pending, self._pending = self._pending, []
        for name, kwargs in pending:
            kicker: AsyncKicker[..., Any] = AsyncKicker(name.value, self._broker, {})
            try:
                await kicker.kiq(**kwargs)
            except Exception:
                logger.exception("Не удалось поставить задачу %s", name.value)
