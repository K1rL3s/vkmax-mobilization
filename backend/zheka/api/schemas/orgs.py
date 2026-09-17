from datetime import datetime

from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.houses import HouseListItem
from zheka.core.enums import OrgRole
from zheka.core.ids import HouseId, OrgId, UserId


class OrgMembership(BaseSchema):
    org_id: OrgId
    name: str
    role: OrgRole
    is_demo: bool


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


class RegisterOrgRequest(BaseSchema):
    inn: str
    license_no: str | None = None
    name: str
    phone: str
    address: str
    house_ids: list[HouseId]


class OrgSettingsResponse(BaseSchema):
    meter_window_day_from: int
    meter_window_day_to: int
    meter_window_always_open: bool
    group_threshold: int
    group_window_hours: int
    phone: str
    reception_note: str | None


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


class OrgInviteItem(BaseSchema):
    code: str
    role: OrgRole
    created_at: datetime
    expires_at: datetime
    max_activations: int
    activations_used: int
    revoked_at: datetime | None
    deeplink: str


class CreateOrgInviteRequest(BaseSchema):
    role: OrgRole
    expires_in_hours: int = 72
    max_activations: int = 1
