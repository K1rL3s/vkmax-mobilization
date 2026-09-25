from datetime import date, datetime

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.ids import (
    AccessRequestId,
    AccessSlotId,
    AccessTargetId,
    FlatId,
    HouseId,
    OrgId,
    UserId,
)


class AccessRequest(ZhekaMutableType):
    id: AccessRequestId = UNSET
    created_at: datetime = UNSET
    org_id: OrgId
    house_id: HouseId
    reason: str
    date: date
    created_by: UserId


class AccessSlot(ZhekaMutableType):
    id: AccessSlotId = UNSET
    access_request_id: AccessRequestId
    starts_at: datetime
    capacity: int


class AccessTarget(ZhekaMutableType):
    id: AccessTargetId = UNSET
    access_request_id: AccessRequestId
    flat_id: FlatId
    slot_id: AccessSlotId | None = None
    responded_at: datetime | None = None
