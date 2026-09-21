from datetime import datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import ResidentRole, ResidentStatus, VerificationStatus
from zheka.core.ids import FlatId, HouseId, ResidentId, UserId, VerificationRequestId
from zheka.core.models import FlatInvite
from zheka.core.services.flats import (
    ACCOUNT_TAIL,
    FlatCardData,
    FlatResidentView,
    VerificationRequestView,
)


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

    @classmethod
    def of(cls, card: FlatCardData) -> Self:
        resident = card.resident
        verified = resident.verified_at is not None
        account_no = card.flat.account_no
        return cls(
            id=card.flat.id,
            house_id=card.flat.house_id,
            address=card.house.address,
            number=card.flat.number,
            role=resident.role,
            verified=verified,
            can_see_charges=resident.can_see_charges,
            can_vote=resident.can_vote,
            meters_count=card.meters_count,
            residents_count=card.residents_count,
            entrance=card.flat.entrance,
            area=card.flat.area,
            account_no=(
                account_no[-ACCOUNT_TAIL:]
                if verified and resident.can_see_charges and account_no is not None
                else None
            ),
            verification_status=card.verification_status,
        )


class VerifyFlatRequest(BaseSchema):
    account_no: str


class VerifyFlatResponse(BaseSchema):
    verified: bool
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
    comment: str | None = None
    reason: str | None = None

    @classmethod
    def of(cls, view: VerificationRequestView) -> Self:
        request = view.request
        return cls(
            id=VerificationRequestId(request.id),
            created_at=request.created_at,
            flat_id=FlatId(view.flat.id),
            flat_number=view.flat.number,
            house_id=HouseId(view.house.id),
            address=view.house.address,
            user_id=UserId(view.user.id),
            user_name=view.user.name,
            account_no=request.account_no,
            status=request.status,
            comment=request.comment,
            reason=request.reason,
        )


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

    @classmethod
    def of(cls, view: FlatResidentView) -> Self:
        resident = view.resident
        return cls(
            resident_id=ResidentId(resident.id),
            user_id=UserId(view.user.id),
            name=view.user.name,
            role=resident.role,
            status=resident.status,
            verified=resident.verified_at is not None,
            is_chairman=resident.is_chairman,
            can_see_charges=resident.can_see_charges,
            can_vote=resident.can_vote,
        )


class FlatInviteItem(BaseSchema):
    code: str
    flat_id: FlatId
    created_at: datetime
    expires_at: datetime
    max_activations: int
    activations_used: int
    revoked_at: datetime | None
    deeplink: str

    @classmethod
    def of(cls, invite: FlatInvite, deeplink: str) -> Self:
        return cls(
            code=invite.code,
            flat_id=FlatId(invite.flat_id),
            created_at=invite.created_at,
            expires_at=invite.expires_at,
            max_activations=invite.max_activations,
            activations_used=invite.activations_used,
            revoked_at=invite.revoked_at,
            deeplink=deeplink,
        )


class CreateFlatInviteRequest(BaseSchema):
    expires_in_hours: int = 72
    max_activations: int = 1
