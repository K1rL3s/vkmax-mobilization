import json
import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from zheka.core.enums import EventType
from zheka.core.ids import UserId
from zheka.infra.database.repos.events import EventsRepo

logger = logging.getLogger(__name__)


class EventsService:
    __slots__ = ("_events_repo",)

    def __init__(self, events_repo: EventsRepo) -> None:
        self._events_repo = events_repo

    async def record(
        self, type: EventType, *, user_id: UserId | None = None, **payload: Any
    ) -> None:
        # аналитика не валит бизнес-действие; default=str спасает datetime и UUID
        try:
            payload = json.loads(json.dumps(payload, default=str))
            await self._events_repo.add(type, user_id, payload)
        except (SQLAlchemyError, ValueError, TypeError):
            logger.exception("Не удалось записать событие %s", type)
