from datetime import date, datetime
from typing import cast

from zheka.base import ZhekaMutableType
from zheka.core.ids import (
    AccessRequestId,
    AccessSlotId,
    AccessTargetId,
    FlatId,
    HouseId,
    OrgId,
    UserId,
)

_UNSET_AT = cast(datetime, None)
_UNSET_ACCESS_REQUEST_ID = cast(AccessRequestId, None)
_UNSET_ACCESS_SLOT_ID = cast(AccessSlotId, None)
_UNSET_ACCESS_TARGET_ID = cast(AccessTargetId, None)


class AccessRequest(ZhekaMutableType):
    id: AccessRequestId = _UNSET_ACCESS_REQUEST_ID
    created_at: datetime = _UNSET_AT
    org_id: OrgId
    house_id: HouseId
    reason: str
    date: date
    created_by: UserId


class AccessSlot(ZhekaMutableType):
    id: AccessSlotId = _UNSET_ACCESS_SLOT_ID
    access_request_id: AccessRequestId
    starts_at: datetime
    capacity: int


class AccessTarget(ZhekaMutableType):
    id: AccessTargetId = _UNSET_ACCESS_TARGET_ID
    access_request_id: AccessRequestId
    flat_id: FlatId
    slot_id: AccessSlotId | None = None
    responded_at: datetime | None = None
