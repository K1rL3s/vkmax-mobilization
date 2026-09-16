from datetime import datetime
from typing import cast

from zheka.base import ZhekaMutableType
from zheka.core.ids import AnnouncementId, HouseId, OrgId, UserId

_UNSET_AT = cast(datetime, None)
_UNSET_ANNOUNCEMENT_ID = cast(AnnouncementId, None)


class Announcement(ZhekaMutableType):
    id: AnnouncementId = _UNSET_ANNOUNCEMENT_ID
    created_at: datetime = _UNSET_AT
    org_id: OrgId
    house_ids: list[HouseId]
    text: str
    channels: list[str]
    created_by: UserId
