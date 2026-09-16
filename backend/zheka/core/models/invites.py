from datetime import datetime
from typing import cast

from zheka.base import ZhekaMutableType
from zheka.core.enums import OrgRole
from zheka.core.ids import FlatId, OrgId, UserId

_UNSET_AT = cast(datetime, None)


class OrgInvite(ZhekaMutableType):
    code: str
    created_at: datetime = _UNSET_AT
    org_id: OrgId
    role: OrgRole
    expires_at: datetime
    max_activations: int
    activations_used: int = 0
    created_by: UserId
    revoked_at: datetime | None = None


class FlatInvite(ZhekaMutableType):
    code: str
    created_at: datetime = _UNSET_AT
    flat_id: FlatId
    created_by: UserId
    expires_at: datetime
    max_activations: int
    activations_used: int = 0
    revoked_at: datetime | None = None
