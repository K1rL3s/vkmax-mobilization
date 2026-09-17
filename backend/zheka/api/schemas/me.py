from datetime import datetime
from typing import Literal

from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.houses import ResidencySummary
from zheka.api.schemas.orgs import OrgMembership
from zheka.core.enums import (
    EventSource,
    EventType,
    NotificationCategory,
    NotificationLevel,
)
from zheka.core.ids import AnnouncementId, UserId


class MeResponse(BaseSchema):
    user_id: UserId
    name: str
    consent_at: datetime | None
    consent_version: str | None
    residencies: list[ResidencySummary]
    orgs: list[OrgMembership]
    is_demo: bool


class ConsentRequest(BaseSchema):
    version: str


class NotificationSettingItem(BaseSchema):
    category: NotificationCategory
    level: NotificationLevel


class NotificationSettingsResponse(BaseSchema):
    settings: list[NotificationSettingItem]


class UpdateNotificationSettingsRequest(BaseSchema):
    settings: list[NotificationSettingItem]


class TrackEventRequest(BaseSchema):
    # клиенту разрешены ровно два события, остальные пишет сервер
    type: Literal[EventType.MINIAPP_OPEN, EventType.ANNOUNCEMENT_CLICK]
    source: EventSource | None = None
    tab: str | None = None
    announcement_id: AnnouncementId | None = None
