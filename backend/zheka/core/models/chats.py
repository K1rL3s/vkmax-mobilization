from datetime import datetime
from typing import cast

from zheka.base import ZhekaMutableType
from zheka.core.ids import ChatPinId, HouseId, MaxChatId, UserId

_UNSET_AT = cast(datetime, None)
_UNSET_PIN_ID = cast(ChatPinId, None)


class Chat(ZhekaMutableType):
    chat_id: MaxChatId
    created_at: datetime = _UNSET_AT
    house_id: HouseId | None = None
    title: str | None = None
    bound_by: UserId | None = None
    bot_is_admin: bool = False
    bound_at: datetime | None = None
    status: str
    pins_mid: str | None = None


class ChatPin(ZhekaMutableType):
    id: ChatPinId = _UNSET_PIN_ID
    created_at: datetime = _UNSET_AT
    chat_id: MaxChatId
    mid: str
    seq: int
    text: str | None = None
    pinned_by: UserId
    unpinned_at: datetime | None = None
