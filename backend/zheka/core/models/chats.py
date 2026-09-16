from datetime import datetime
from typing import cast

from zheka.base import ZhekaMutableType
from zheka.core.ids import HouseId, MaxChatId, UserId

_UNSET_AT = cast(datetime, None)


class Chat(ZhekaMutableType):
    chat_id: MaxChatId
    created_at: datetime = _UNSET_AT
    house_id: HouseId | None = None
    title: str | None = None
    bound_by: UserId | None = None
    bot_is_admin: bool = False
    bound_at: datetime | None = None
    status: str
