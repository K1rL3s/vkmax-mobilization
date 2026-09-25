from datetime import datetime
from typing import Any

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.ids import EventId, UserId


class Event(ZhekaMutableType):
    id: EventId = UNSET
    created_at: datetime = UNSET
    user_id: UserId | None = None
    type: str
    payload: Any
