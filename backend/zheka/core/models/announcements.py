from dataclasses import field
from datetime import datetime
from typing import Self

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.enums import NoticeStatus, RequestCategory, ResidentRole
from zheka.core.ids import AnnouncementId, FlatId, HouseId, OrgId, PollId, UserId
from zheka.core.models.residents import Resident


class Announcement(ZhekaMutableType):
    id: AnnouncementId = UNSET
    created_at: datetime = UNSET
    org_id: OrgId
    house_ids: list[HouseId]
    text: str
    channels: list[str]
    created_by: UserId
    recipients_count: int = 0
    urgent: bool = False
    delivered_direct: int | None = None
    delivered_chat: int | None = None
    entrances: list[int] | None = None
    flat_ids: list[FlatId] | None = None
    poll_id: PollId | None = None
    works_category: RequestCategory | None = None
    works_from: datetime | None = None
    works_until: datetime | None = None
    documents: list[dict[str, str]] = field(default_factory=list)

    @property
    def delivered_count(self) -> int | None:
        if self.delivered_direct is None or self.delivered_chat is None:
            return None
        return self.delivered_direct + self.delivered_chat

    @property
    def flats_count(self) -> int | None:
        return None if self.flat_ids is None else len(self.flat_ids)


class NoticeDelivery(ZhekaMutableType):
    announcement_id: AnnouncementId
    user_id: UserId
    house_id: HouseId
    flat_id: FlatId | None = None
    role: ResidentRole | None = None
    verified: bool = False
    status: NoticeStatus = NoticeStatus.PENDING
    at: datetime | None = None

    @classmethod
    def of(cls, announcement_id: AnnouncementId, resident: Resident) -> Self:
        return cls(
            announcement_id=announcement_id,
            user_id=resident.user_id,
            house_id=resident.house_id,
            flat_id=resident.flat_id,
            role=resident.role,
            verified=resident.verified_at is not None,
        )
