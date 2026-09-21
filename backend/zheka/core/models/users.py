from datetime import datetime
from typing import cast

from zheka.base import ZhekaMutableType
from zheka.core.enums import NotificationCategory, NotificationLevel
from zheka.core.ids import MaxChatId, MaxUserId, NotificationSettingId, UserId

_UNSET_AT = cast(datetime, None)
_UNSET_USER_ID = cast(UserId, None)
_UNSET_NOTIFICATION_SETTING_ID = cast(NotificationSettingId, None)


class User(ZhekaMutableType):
    id: UserId = _UNSET_USER_ID
    created_at: datetime = _UNSET_AT
    updated_at: datetime = _UNSET_AT
    max_user_id: MaxUserId
    name: str
    username: str | None = None
    consent_version: str | None = None
    consent_at: datetime | None = None
    bot_stopped_at: datetime | None = None
    max_chat_id: MaxChatId | None = None


class NotificationSetting(ZhekaMutableType):
    id: NotificationSettingId = _UNSET_NOTIFICATION_SETTING_ID
    user_id: UserId
    category: NotificationCategory
    level: NotificationLevel
