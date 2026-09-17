from datetime import datetime
from typing import Literal, Self

from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.houses import ResidencySummary
from zheka.api.schemas.orgs import OrgMembership
from zheka.core.enums import (
    EventSource,
    EventType,
    NotificationCategory,
    NotificationLevel,
)
from zheka.core.ids import AnnouncementId, OrgId, UserId
from zheka.core.services.profile import MeView


class MeResponse(BaseSchema):
    user_id: UserId
    name: str
    consent_at: datetime | None
    consent_version: str | None
    residencies: list[ResidencySummary]
    orgs: list[OrgMembership]
    is_demo: bool

    @classmethod
    def of(cls, view: MeView) -> Self:
        return cls(
            user_id=UserId(view.user.id),
            name=view.user.name,
            consent_at=view.user.consent_at,
            consent_version=view.user.consent_version,
            residencies=[
                ResidencySummary.of(residency) for residency in view.residencies
            ],
            orgs=[
                OrgMembership(
                    org_id=OrgId(membership.org.id),
                    name=membership.org.name,
                    role=membership.member.role,
                    is_demo=membership.org.is_demo,
                )
                for membership in view.orgs
            ],
            is_demo=view.is_demo,
        )


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
