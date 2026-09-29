from datetime import datetime

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.enums import NotificationCategory, NotificationLevel
from zheka.core.ids import MaxChatId, MaxUserId, NotificationSettingId, UserId


class User(ZhekaMutableType):
    id: UserId = UNSET
    created_at: datetime = UNSET
    updated_at: datetime = UNSET
    max_user_id: MaxUserId
    name: str
    username: str | None = None
    consent_version: str | None = None
    consent_at: datetime | None = None
    bot_stopped_at: datetime | None = None
    max_chat_id: MaxChatId | None = None
    phone: str | None = None
    phone_verified_at: datetime | None = None

    @property
    def in_dialog(self) -> bool:
        return (
            self.max_user_id >= 0
            and self.max_chat_id is not None
            and self.bot_stopped_at is None
        )


class NotificationSetting(ZhekaMutableType):
    id: NotificationSettingId = UNSET
    user_id: UserId
    category: NotificationCategory
    level: NotificationLevel
