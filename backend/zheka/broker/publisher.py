import logging
from typing import Any

from taskiq import AsyncBroker
from taskiq.kicker import AsyncKicker

from zheka.broker.task_names import TaskName

logger = logging.getLogger(__name__)


class TaskPublisher:
    __slots__ = ("_broker", "_pending")

    def __init__(self, broker: AsyncBroker) -> None:
        self._broker = broker
        self._pending: list[tuple[TaskName, dict[str, Any]]] = []

    def publish(self, name: TaskName, **kwargs: Any) -> None:
        # синхронно и без сети: задача уезжает во flush, после коммита, иначе
        # откатившийся запрос успел бы разослать сообщения о том, чего нет
        self._pending.append((name, kwargs))

    async def flush(self) -> None:
        # список забирается целиком: повторный flush не отправит то же самое
        pending, self._pending = self._pending, []
        for name, kwargs in pending:
            kicker: AsyncKicker[..., Any] = AsyncKicker(name.value, self._broker, {})
            try:
                await kicker.kiq(**kwargs)
            except Exception:
                # одна не уехавшая задача не отменяет остальные: транзакция
                # уже закоммичена, откатывать нечего
                logger.exception("Не удалось поставить задачу %s", name.value)
