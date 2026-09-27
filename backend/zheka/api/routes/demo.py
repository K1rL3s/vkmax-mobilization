from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentUserDep, RequireConsentDep
from zheka.api.schemas.demo import DemoActivationRequest, DemoActivationResponse
from zheka.api.schemas.houses import ResidencySummary
from zheka.api.schemas.orgs import OrgMembership
from zheka.core.enums import OrgRole
from zheka.core.errors import NotEnoughRights
from zheka.core.services.demo import (
    API_CHECKER_DEMO_NUMBER,
    API_CHECKER_MAX_USER_ID,
    CHECKER_ONLY,
    DemoService,
)

router = APIRouter(tags=["Демо"], route_class=DishkaRoute)


@router.post("/demo/activate", summary="Выдать демо-доступ жителя и сотрудника")
async def activate_demo(
    current_user: CurrentUserDep,
    current_account: RequireConsentDep,
    demo_service: FromDishka[DemoService],
    body: DemoActivationRequest | None = None,
) -> DemoActivationResponse:
    request = body or DemoActivationRequest()
    if current_user.user.id == API_CHECKER_MAX_USER_ID and (
        request.number != API_CHECKER_DEMO_NUMBER or request.admin
    ):
        raise NotEnoughRights(CHECKER_ONLY)
    access = await demo_service.activate(
        current_account.user_id,
        request.number,
        OrgRole.ADMIN if request.admin else OrgRole.EMPLOYEE,
    )
    return DemoActivationResponse(
        org=OrgMembership.of(access.membership),
        residency=ResidencySummary.of(access.residency),
    )
