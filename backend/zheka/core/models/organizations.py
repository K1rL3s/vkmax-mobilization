from datetime import datetime
from typing import cast

from zheka.base import ZhekaMutableType, Zoned
from zheka.core.enums import OrgRole
from zheka.core.ids import OrgId, OrgMemberId, UserId

_UNSET_AT = cast(datetime, None)
_UNSET_ORG_ID = cast(OrgId, None)
_UNSET_ORG_MEMBER_ID = cast(OrgMemberId, None)


class Organization(ZhekaMutableType, Zoned):
    id: OrgId = _UNSET_ORG_ID
    created_at: datetime = _UNSET_AT
    name: str
    inn: str
    license_no: str | None = None
    phone: str
    address: str
    reception_note: str | None = None
    registered_at: datetime | None = None
    is_demo: bool = False
    # имя зоны IANA офиса: окна приема, записи и недели дашборда
    timezone: str


class OrgSettings(ZhekaMutableType):
    org_id: OrgId
    updated_at: datetime = _UNSET_AT
    meter_window_day_from: int = 15
    meter_window_day_to: int = 25
    meter_window_always_open: bool = False
    group_threshold: int = 3
    group_window_hours: int = 24


class OrgMember(ZhekaMutableType):
    id: OrgMemberId = _UNSET_ORG_MEMBER_ID
    created_at: datetime = _UNSET_AT
    org_id: OrgId
    user_id: UserId
    role: OrgRole
