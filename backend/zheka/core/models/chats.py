from datetime import datetime

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.ids import ChatPinId, HouseId, MaxChatId, UserId


class Chat(ZhekaMutableType):
    chat_id: MaxChatId
    created_at: datetime = UNSET
    house_id: HouseId | None = None
    title: str | None = None
    bound_by: UserId | None = None
    bot_is_admin: bool = False
    bound_at: datetime | None = None
    status: str
    pins_mid: str | None = None


class ChatPin(ZhekaMutableType):
    id: ChatPinId = UNSET
    created_at: datetime = UNSET
    chat_id: MaxChatId
    mid: str
    seq: int
    text: str | None = None
    pinned_by: UserId
    unpinned_at: datetime | None = None
