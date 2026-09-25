from datetime import datetime

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.enums import ResidentRole, ResidentStatus, VerificationStatus
from zheka.core.ids import (
    DemandSignalId,
    FlatId,
    HouseId,
    ResidentId,
    UserId,
    VerificationRequestId,
)


class Resident(ZhekaMutableType):
    id: ResidentId = UNSET
    created_at: datetime = UNSET
    user_id: UserId
    house_id: HouseId
    flat_id: FlatId | None = None
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
    id: VerificationRequestId = UNSET
    created_at: datetime = UNSET
    flat_id: FlatId
    user_id: UserId
    account_no: str
    comment: str | None = None
    status: VerificationStatus
    decided_by: UserId | None = None
    decided_at: datetime | None = None
    reason: str | None = None


class DemandSignal(ZhekaMutableType):
    id: DemandSignalId = UNSET
    created_at: datetime = UNSET
    house_id: HouseId
    user_id: UserId
