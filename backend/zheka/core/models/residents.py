from datetime import datetime
from typing import cast

from zheka.base import ZhekaMutableType
from zheka.core.enums import ResidentRole, ResidentStatus, VerificationStatus
from zheka.core.ids import (
    DemandSignalId,
    FlatId,
    HouseId,
    ResidentId,
    UserId,
    VerificationRequestId,
)

_UNSET_AT = cast(datetime, None)
_UNSET_RESIDENT_ID = cast(ResidentId, None)
_UNSET_VERIFICATION_REQUEST_ID = cast(VerificationRequestId, None)
_UNSET_DEMAND_SIGNAL_ID = cast(DemandSignalId, None)


class Resident(ZhekaMutableType):
    id: ResidentId = _UNSET_RESIDENT_ID
    created_at: datetime = _UNSET_AT
    user_id: UserId
    house_id: HouseId
    flat_id: FlatId | None = None
    # номер квартиры, которой еще нет в доме: УК заводит квартиры не везде
    flat_number: str | None = None
    role: ResidentRole
    can_see_charges: bool = True
    can_vote: bool = True
    verified_at: datetime | None = None
    verified_by: UserId | None = None
    status: ResidentStatus = ResidentStatus.ACTIVE
    block_reason: str | None = None
    is_chairman: bool = False


class VerificationRequest(ZhekaMutableType):
    id: VerificationRequestId = _UNSET_VERIFICATION_REQUEST_ID
    created_at: datetime = _UNSET_AT
    flat_id: FlatId
    user_id: UserId
    account_no: str
    # пояснение жителя к запросу и причина отказа УК: оба видны в админке
    comment: str | None = None
    status: VerificationStatus
    decided_by: UserId | None = None
    decided_at: datetime | None = None
    reason: str | None = None


class DemandSignal(ZhekaMutableType):
    id: DemandSignalId = _UNSET_DEMAND_SIGNAL_ID
    created_at: datetime = _UNSET_AT
    house_id: HouseId
    user_id: UserId
