from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentOrgDep
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.api.schemas.polls import AdminPollListItem, CreateOrgPollRequest, PollCard
from zheka.core.enums import PollStatus
from zheka.core.ids import HouseId

router = APIRouter(tags=["Админка: опросы"], route_class=DishkaRoute)


@router.get("/admin/polls", summary="Опросы организации")
async def list_org_polls(
    current_org: CurrentOrgDep,
    house_id: HouseId | None = None,
    status: PollStatus | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AdminPollListItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post("/admin/polls", summary="Создать опрос от организации")
async def create_org_poll(
    current_org: CurrentOrgDep,
    body: CreateOrgPollRequest,
) -> PollCard:
    raise NotImplementedError("ещё не реализовано")
