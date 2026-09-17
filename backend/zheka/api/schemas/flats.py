from datetime import datetime

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import ResidentRole, ResidentStatus, VerificationStatus
from zheka.core.ids import FlatId, HouseId, ResidentId, UserId, VerificationRequestId


class FlatCard(BaseSchema):
    id: FlatId
    house_id: HouseId
    address: str
    number: str
    role: ResidentRole
    verified: bool
    can_see_charges: bool
    can_vote: bool
    meters_count: int
    residents_count: int
    entrance: int | None = None
    area: int | None = Field(
        default=None, description="Площадь в сотых долях квадратного метра"
    )
    account_no: str | None = None
    verification_status: VerificationStatus | None = None


class VerifyFlatRequest(BaseSchema):
    account_no: str


class VerifyFlatResponse(BaseSchema):
    verified: bool
    # что делать дальше, если лицевой счет не сошелся
    detail: str
    verification_status: VerificationStatus | None = None


class FlatVerificationRequest(BaseSchema):
    account_no: str
    comment: str | None = None


class VerificationRequestItem(BaseSchema):
    id: VerificationRequestId
    created_at: datetime
    flat_id: FlatId
    flat_number: str
    house_id: HouseId
    address: str
    user_id: UserId
    user_name: str
    account_no: str
    status: VerificationStatus


class RejectVerificationRequest(BaseSchema):
    reason: str


class FlatResidentItem(BaseSchema):
    resident_id: ResidentId
    user_id: UserId
    name: str
    role: ResidentRole
    status: ResidentStatus
    verified: bool
    is_chairman: bool
    can_see_charges: bool
    can_vote: bool


class FlatInviteItem(BaseSchema):
    code: str
    flat_id: FlatId
    created_at: datetime
    expires_at: datetime
    max_activations: int
    activations_used: int
    revoked_at: datetime | None
    deeplink: str


class CreateFlatInviteRequest(BaseSchema):
    expires_in_hours: int = 72
    max_activations: int = 1
