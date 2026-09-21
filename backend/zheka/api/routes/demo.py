from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import RequireConsentDep
from zheka.api.schemas.demo import DemoActivationResponse
from zheka.api.schemas.houses import ResidencySummary
from zheka.api.schemas.orgs import OrgMembership
from zheka.core.services.demo import DemoService

router = APIRouter(tags=["Демо"], route_class=DishkaRoute)


@router.post("/demo/activate", summary="Выдать демо-доступ жителя и сотрудника")
async def activate_demo(
    current_account: RequireConsentDep, demo_service: FromDishka[DemoService]
) -> DemoActivationResponse:
    access = await demo_service.activate(current_account.user_id)
    return DemoActivationResponse(
        org=OrgMembership.of(access.membership),
        residency=ResidencySummary.of(access.residency),
    )
