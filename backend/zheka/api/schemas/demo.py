from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.houses import ResidencySummary
from zheka.api.schemas.orgs import OrgMembership


class ActivateDemoRequest(BaseSchema):
    code: str | None = None


class DemoActivationResponse(BaseSchema):
    org: OrgMembership | None = None
    residency: ResidencySummary | None = None
