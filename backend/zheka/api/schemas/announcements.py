from datetime import datetime

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import AnnouncementChannel
from zheka.core.ids import AnnouncementId, HouseId


class AnnouncementItem(BaseSchema):
    id: AnnouncementId
    created_at: datetime
    text: str
    house_ids: list[HouseId]
    channels: list[AnnouncementChannel]
    org_name: str | None = None
    recipients_count: int = 0


class CreateAnnouncementRequest(BaseSchema):
    house_ids: list[HouseId]
    text: str
    # дефолт продукта - только домовой чат
    channels: list[AnnouncementChannel] = Field(
        default_factory=lambda: [AnnouncementChannel.CHAT],
    )
