from collections.abc import Mapping
from datetime import datetime
from typing import Literal, Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema, FreeText
from zheka.api.schemas.houses import ResidencySummary
from zheka.api.schemas.orgs import OrgMembership
from zheka.core.enums import (
    EventSource,
    EventType,
    NotificationCategory,
    NotificationLevel,
    TextSize,
)
from zheka.core.ids import AnnouncementId, UserId
from zheka.core.services.profile import MeView


class MeResponse(BaseSchema):
    user_id: UserId
    name: str
    consent_at: datetime | None
    consent_version: str | None
    residencies: list[ResidencySummary]
    orgs: list[OrgMembership]
    is_demo: bool
    phone: str | None = Field(
        default=None,
        description="Номер, подтвержденный MAX, в формате +79991234567",
    )
    text_size: TextSize = Field(
        description="Размер текста в мини-приложении: обычный, крупный, очень крупный",
    )

    @classmethod
    def of(cls, view: MeView) -> Self:
        return cls(
            user_id=view.user.id,
            name=view.user.name,
            consent_at=view.user.consent_at,
            consent_version=view.user.consent_version,
            residencies=[
                ResidencySummary.of(residency) for residency in view.residencies
            ],
            orgs=[OrgMembership.of(membership) for membership in view.orgs],
            is_demo=view.is_demo,
            phone=view.user.phone,
            text_size=view.user.text_size,
        )


class VerifyPhoneRequest(BaseSchema):
    phone: str = Field(max_length=32)
    auth_date: str = Field(max_length=32, description="authDate из requestContact")
    hash: str = Field(max_length=128)


class ConsentRequest(BaseSchema):
    version: str


class NotificationSettingItem(BaseSchema):
    category: NotificationCategory
    level: NotificationLevel


class NotificationSettingsResponse(BaseSchema):
    settings: list[NotificationSettingItem]

    @classmethod
    def of(cls, levels: Mapping[NotificationCategory, NotificationLevel]) -> Self:
        return cls(
            settings=[
                NotificationSettingItem(category=category, level=level)
                for category, level in levels.items()
            ],
        )


class UpdateNotificationSettingsRequest(BaseSchema):
    settings: list[NotificationSettingItem]


class TrackEventRequest(BaseSchema):
    type: Literal[EventType.MINIAPP_OPEN, EventType.ANNOUNCEMENT_CLICK]
    source: EventSource | None = None
    tab: FreeText | None = None
    announcement_id: AnnouncementId | None = None


class UpdateAppearanceRequest(BaseSchema):
    text_size: TextSize
