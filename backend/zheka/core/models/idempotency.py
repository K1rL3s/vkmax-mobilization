from datetime import datetime
from typing import Any
from uuid import UUID

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.ids import UserId


class IdempotencyKey(ZhekaMutableType):
    user_id: UserId
    key: UUID
    route: str
    response: dict[str, Any] | None = None
    created_at: datetime = UNSET
