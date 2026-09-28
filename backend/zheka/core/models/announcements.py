from datetime import datetime

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.ids import AnnouncementId, HouseId, OrgId, UserId


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

    @property
    def delivered_count(self) -> int | None:
        if self.delivered_direct is None or self.delivered_chat is None:
            return None
        return self.delivered_direct + self.delivered_chat
