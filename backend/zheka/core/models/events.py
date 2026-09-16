from datetime import datetime
from typing import Any, cast

from zheka.base import ZhekaMutableType
from zheka.core.ids import EventId, UserId

_UNSET_AT = cast(datetime, None)
_UNSET_EVENT_ID = cast(EventId, None)


class Event(ZhekaMutableType):
    id: EventId = _UNSET_EVENT_ID
    created_at: datetime = _UNSET_AT
    user_id: UserId | None = None
    type: str
    payload: Any
