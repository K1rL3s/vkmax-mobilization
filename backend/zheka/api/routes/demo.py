from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import RequireConsentDep
from zheka.api.schemas.demo import ActivateDemoRequest, DemoActivationResponse

router = APIRouter(tags=["Демо"], route_class=DishkaRoute)


@router.post("/demo/activate", summary="Выдать демо-доступ жителя и сотрудника")
async def activate_demo(
    current_account: RequireConsentDep,
    body: ActivateDemoRequest,
) -> DemoActivationResponse:
    raise NotImplementedError("ещё не реализовано")
