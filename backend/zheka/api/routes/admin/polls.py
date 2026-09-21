from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentOrgDep
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.api.schemas.polls import AdminPollListItem, CreateOrgPollRequest, PollCard
from zheka.core.enums import PollStatus
from zheka.core.ids import HouseId
from zheka.core.services.polls import PollsService

router = APIRouter(tags=["Админка: опросы"], route_class=DishkaRoute)


@router.get("/admin/polls", summary="Опросы организации")
async def list_org_polls(
    current_org: CurrentOrgDep,
    polls_service: FromDishka[PollsService],
    house_id: HouseId | None = None,
    status: PollStatus | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AdminPollListItem]:
    items, total = await polls_service.list_org_polls(
        current_org.org_id,
        current_org.user_id,
        house_id,
        status,
        limit,
        offset,
    )
    return Page(
        items=[AdminPollListItem.of_admin(item) for item in items],
        total=total,
    )


@router.post("/admin/polls", summary="Создать опрос от организации")
async def create_org_poll(
    current_org: CurrentOrgDep,
    body: CreateOrgPollRequest,
    polls_service: FromDishka[PollsService],
) -> PollCard:
    card = await polls_service.create(
        current_org.user_id,
        body.house_id,
        body.draft(),
        org_id=current_org.org_id,
    )
    return PollCard.of_card(card)
