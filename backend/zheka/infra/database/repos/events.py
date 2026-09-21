from collections.abc import Collection
from datetime import datetime
from typing import Any

from sqlalchemy import select, true

from zheka.core.enums import EventType
from zheka.core.ids import UserId
from zheka.infra.database.models import Event
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.events import events_table


class EventsRepo(BaseAlchemyRepo):
    async def add(
        self,
        type: EventType,
        user_id: UserId | None,
        payload: dict[str, Any],
    ) -> None:
        # savepoint: неудачная запись события не откатывает транзакцию вызывающего
        async with self._session.begin_nested():
            self._session.add(Event(user_id=user_id, type=type.value, payload=payload))

    async def users_with(
        self,
        type: EventType,
        user_ids: Collection[UserId],
        payload: dict[str, Any],
        since: datetime | None = None,
    ) -> set[UserId]:
        if not user_ids:
            return set()
        stmt = select(events_table.c.user_id).where(
            events_table.c.type == type.value,
            events_table.c.user_id.in_(user_ids),
            events_table.c.payload.contains(payload),
            true() if since is None else events_table.c.created_at >= since,
        )
        result = await self._session.execute(stmt)
        return {UserId(user_id) for user_id in result.scalars().all()}
