from datetime import datetime

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.enums import OrgRole
from zheka.core.ids import FlatId, OrgId, UserId


class OrgInvite(ZhekaMutableType):
    code: str
    created_at: datetime = UNSET
    org_id: OrgId
    role: OrgRole
    expires_at: datetime
    max_activations: int
    activations_used: int = 0
    created_by: UserId
    revoked_at: datetime | None = None


class FlatInvite(ZhekaMutableType):
    code: str
    created_at: datetime = UNSET
    flat_id: FlatId
    created_by: UserId
    expires_at: datetime
    max_activations: int
    activations_used: int = 0
    revoked_at: datetime | None = None
