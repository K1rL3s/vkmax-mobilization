from typing import Any

from zheka.core.enums import EventType
from zheka.core.ids import UserId
from zheka.infra.database.models import Event
from zheka.infra.database.repos.base import BaseAlchemyRepo


class EventsRepo(BaseAlchemyRepo):
    async def add(
        self,
        type: EventType,
        user_id: UserId | None,
        payload: dict[str, Any],
    ) -> None:
        # savepoint: если запись события не проходит (нарушение FK,
        # несериализуемый payload), откатывается только она, а не вся
        # бизнес-транзакция вызывающего кода
        async with self._session.begin_nested():
            self._session.add(Event(user_id=user_id, type=type.value, payload=payload))
