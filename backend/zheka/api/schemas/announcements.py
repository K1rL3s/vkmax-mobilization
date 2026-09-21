from datetime import datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import AnnouncementChannel
from zheka.core.ids import AnnouncementId, HouseId
from zheka.core.services.announcements import AnnouncementData


class AnnouncementItem(BaseSchema):
    id: AnnouncementId
    created_at: datetime
    text: str
    house_ids: list[HouseId]
    channels: list[AnnouncementChannel]
    org_name: str | None = None
    recipients_count: int = Field(
        default=0,
        description=(
            "Сколько адресатов было на момент отправки: по одному на жителя "
            "для канала direct и по одному на привязанный чат для канала chat"
        ),
    )
    houses_without_chat: list[HouseId] = Field(
        default_factory=list,
        description=(
            "Дома, у которых не привязан чат, поэтому объявление туда не ушло. "
            "Заполняется только при создании объявления"
        ),
    )

    @classmethod
    def of(cls, data: AnnouncementData) -> Self:
        announcement = data.announcement
        return cls(
            id=announcement.id,
            created_at=announcement.created_at,
            text=announcement.text,
            house_ids=list(announcement.house_ids),
            channels=[
                AnnouncementChannel(channel) for channel in announcement.channels
            ],
            org_name=data.org_name,
            recipients_count=announcement.recipients_count,
            houses_without_chat=list(data.houses_without_chat),
        )


class CreateAnnouncementRequest(BaseSchema):
    house_ids: list[HouseId]
    text: str
    channels: list[AnnouncementChannel] = Field(
        default_factory=lambda: [AnnouncementChannel.CHAT]
    )
