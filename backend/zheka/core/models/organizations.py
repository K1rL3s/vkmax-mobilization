from datetime import datetime

from zheka.base import UNSET, ZhekaMutableType, Zoned
from zheka.core.enums import OrgRole
from zheka.core.ids import OrgId, OrgMemberId, UserId


class Organization(ZhekaMutableType, Zoned):
    id: OrgId = UNSET
    created_at: datetime = UNSET
    name: str
    inn: str
    license_no: str | None = None
    phone: str
    address: str
    reception_note: str | None = None
    registered_at: datetime | None = None
    is_demo: bool = False
    timezone: str


class OrgSettings(ZhekaMutableType):
    org_id: OrgId
    updated_at: datetime = UNSET
    meter_window_day_from: int = 15
    meter_window_day_to: int = 25
    meter_window_always_open: bool = False
    group_threshold: int = 3
    group_window_hours: int = 24


class OrgMember(ZhekaMutableType):
    id: OrgMemberId = UNSET
    created_at: datetime = UNSET
    org_id: OrgId
    user_id: UserId
    role: OrgRole
