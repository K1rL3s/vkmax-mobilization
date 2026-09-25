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
