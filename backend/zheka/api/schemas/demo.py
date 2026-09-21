from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.houses import ResidencySummary
from zheka.api.schemas.orgs import OrgMembership


class DemoActivationResponse(BaseSchema):
    org: OrgMembership
    residency: ResidencySummary
