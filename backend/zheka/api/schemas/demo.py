from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.houses import ResidencySummary
from zheka.api.schemas.orgs import OrgMembership
from zheka.core.services.demo import DEMO_INNS


class DemoActivationResponse(BaseSchema):
    org: OrgMembership
    residency: ResidencySummary


class DemoActivationRequest(BaseSchema):
    number: int = Field(
        default=1,
        ge=1,
        le=len(DEMO_INNS),
        description="Номер демо-УК, как N в ссылке demo_..._N",
    )
    admin: bool = Field(
        default=False,
        description="Выдать роль администратора, а не сотрудника",
    )
