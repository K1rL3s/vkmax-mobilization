from datetime import datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import AnnouncementChannel
from zheka.core.ids import AnnouncementId, HouseId
from zheka.core.services.announcements import (
    ANNOUNCEMENT_TEXT_LIMIT,
    AnnouncementData,
)


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
    urgent: bool = Field(
        default=False,
        description="Срочное: авария, отключение. Житель видит его выделенным",
    )

    @classmethod
    def of(cls, data: AnnouncementData) -> Self:
        return cls.model_validate(data.announcement).model_copy(
            update={
                "org_name": data.org_name,
                "houses_without_chat": list(data.houses_without_chat),
            },
        )


class CreateAnnouncementRequest(BaseSchema):
    house_ids: list[HouseId]
    text: str = Field(
        description=f"Текст объявления, до {ANNOUNCEMENT_TEXT_LIMIT} символов",
    )
    channels: list[AnnouncementChannel] = Field(
        default_factory=lambda: [AnnouncementChannel.CHAT],
    )
    urgent: bool = Field(
        default=False,
        description="Срочное: авария, отключение. Житель видит его выделенным",
    )
