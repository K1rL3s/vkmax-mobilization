from datetime import datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.houses import HouseListItem
from zheka.core.enums import OrgRole
from zheka.core.ids import OrgId, UserId
from zheka.core.models import OrgInvite
from zheka.core.services.orgs import (
    OrgCardView,
    OrgLookupView,
    OrgMemberView,
    OrgSettingsView,
)
from zheka.core.services.profile import OrgMembershipView


class OrgMembership(BaseSchema):
    org_id: OrgId
    name: str
    role: OrgRole
    is_demo: bool

    @classmethod
    def of(cls, view: OrgMembershipView) -> Self:
        return cls(
            org_id=view.org.id,
            name=view.org.name,
            role=view.member.role,
            is_demo=view.org.is_demo,
        )


class OrgCard(BaseSchema):
    id: OrgId
    name: str
    inn: str
    license_no: str | None
    phone: str
    address: str
    reception_note: str | None
    registered_at: datetime | None
    is_demo: bool
    houses_count: int
    members_count: int

    @classmethod
    def of(cls, card: OrgCardView) -> Self:
        org = card.org
        return cls(
            id=org.id,
            name=org.name,
            inn=org.inn,
            license_no=org.license_no,
            phone=org.phone,
            address=org.address,
            reception_note=org.reception_note,
            registered_at=org.registered_at,
            is_demo=org.is_demo,
            houses_count=card.houses_count,
            members_count=card.members_count,
        )


class OrgLookupRequest(BaseSchema):
    inn: str | None = None
    license_no: str | None = None


class OrgLookupResponse(BaseSchema):
    found: bool
    already_registered: bool
    name: str | None = None
    inn: str | None = None
    license_no: str | None = None
    phone: str | None = None
    address: str | None = None
    houses: list[HouseListItem]

    @classmethod
    def of(cls, view: OrgLookupView) -> Self:
        org = view.org
        return cls(
            found=org is not None,
            already_registered=org is not None and org.registered_at is not None,
            name=None if org is None else org.name,
            inn=None if org is None else org.inn,
            license_no=None if org is None else org.license_no,
            phone=None if org is None else org.phone,
            address=None if org is None else org.address,
            houses=[HouseListItem.of(found) for found in view.houses],
        )


class RegisterOrgRequest(BaseSchema):
    deeplink_code: str = Field(description="Скрытый код из диплинка регистрации")
    inn: str
    license_no: str | None = None
    name: str
    phone: str
    address: str


class OrgSettingsResponse(BaseSchema):
    meter_window_day_from: int = Field(description="День месяца, 1-28")
    meter_window_day_to: int = Field(description="День месяца, 1-28")
    meter_window_always_open: bool
    group_threshold: int
    group_window_hours: int
    phone: str
    reception_note: str | None

    @classmethod
    def of(cls, view: OrgSettingsView) -> Self:
        settings = view.settings
        return cls(
            meter_window_day_from=settings.meter_window_day_from,
            meter_window_day_to=settings.meter_window_day_to,
            meter_window_always_open=settings.meter_window_always_open,
            group_threshold=settings.group_threshold,
            group_window_hours=settings.group_window_hours,
            phone=view.org.phone,
            reception_note=view.org.reception_note,
        )


class UpdateOrgSettingsRequest(BaseSchema):
    meter_window_day_from: int
    meter_window_day_to: int
    meter_window_always_open: bool
    group_threshold: int
    group_window_hours: int
    phone: str
    reception_note: str | None = None


class OrgMemberItem(BaseSchema):
    user_id: UserId
    name: str
    username: str | None
    role: OrgRole
    created_at: datetime
    can_remove: bool

    @classmethod
    def of(cls, view: OrgMemberView, can_remove: bool) -> Self:
        return cls(
            user_id=view.user.id,
            name=view.user.name,
            username=view.user.username,
            role=view.member.role,
            created_at=view.member.created_at,
            can_remove=can_remove,
        )


class OrgInviteItem(BaseSchema):
    code: str
    role: OrgRole
    created_at: datetime
    expires_at: datetime
    max_activations: int
    activations_used: int
    revoked_at: datetime | None
    deeplink: str

    @classmethod
    def of(cls, invite: OrgInvite, deeplink: str) -> Self:
        return cls(
            code=invite.code,
            role=invite.role,
            created_at=invite.created_at,
            expires_at=invite.expires_at,
            max_activations=invite.max_activations,
            activations_used=invite.activations_used,
            revoked_at=invite.revoked_at,
            deeplink=deeplink,
        )


class CreateOrgInviteRequest(BaseSchema):
    role: OrgRole
    expires_in_hours: int = 72
    max_activations: int = 1
