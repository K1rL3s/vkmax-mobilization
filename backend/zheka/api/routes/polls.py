from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import RequireConsentDep, ResidencyForHouseDep
from zheka.api.schemas.polls import (
    CreatePollRequest,
    PollCard,
    PollListItem,
    PollNonVoterItem,
    PollResults,
    VoteRequest,
)
from zheka.core.enums import EventSource, PollStatus
from zheka.core.ids import HouseId, PollId
from zheka.core.services.polls import PollsService

router = APIRouter(tags=["Опросы"], route_class=DishkaRoute)


@router.get("/houses/{house_id}/polls", summary="Опросы дома")
async def list_polls(
    house_id: HouseId,
    residency: ResidencyForHouseDep,
    polls_service: FromDishka[PollsService],
    status: PollStatus | None = None,
) -> list[PollListItem]:
    items = await polls_service.list_polls(house_id, residency.user_id, status)
    return [PollListItem.of(item) for item in items]


@router.post("/houses/{house_id}/polls", summary="Создать опрос дома")
async def create_poll(
    house_id: HouseId,
    residency: ResidencyForHouseDep,
    body: CreatePollRequest,
    polls_service: FromDishka[PollsService],
) -> PollCard:
    card = await polls_service.create(
        residency.user_id,
        house_id,
        body.draft(),
        org_id=None,
    )
    return PollCard.of_card(card)


@router.get("/polls/{poll_id}", summary="Карточка опроса")
async def get_poll(
    poll_id: PollId,
    current_account: RequireConsentDep,
    polls_service: FromDishka[PollsService],
) -> PollCard:
    card = await polls_service.get_card(poll_id, current_account.user_id)
    return PollCard.of_card(card)


@router.post("/polls/{poll_id}/vote", summary="Проголосовать")
async def vote_in_poll(
    poll_id: PollId,
    current_account: RequireConsentDep,
    body: VoteRequest,
    polls_service: FromDishka[PollsService],
) -> PollResults:
    results = await polls_service.vote(
        poll_id,
        current_account.user_id,
        body.option_ids,
        EventSource.MINIAPP,
    )
    return PollResults.of(results)


@router.get("/polls/{poll_id}/results", summary="Результаты и прогноз кворума")
async def get_poll_results(
    poll_id: PollId,
    current_account: RequireConsentDep,
    polls_service: FromDishka[PollsService],
) -> PollResults:
    results = await polls_service.results(poll_id, current_account.user_id)
    return PollResults.of(results)


@router.get("/polls/{poll_id}/non-voters", summary="Непроголосовавшие квартиры")
async def list_poll_non_voters(
    poll_id: PollId,
    current_account: RequireConsentDep,
    polls_service: FromDishka[PollsService],
) -> list[PollNonVoterItem]:
    flats = await polls_service.non_voters(poll_id, current_account.user_id)
    return [PollNonVoterItem.of(flat) for flat in flats]


@router.post("/polls/{poll_id}/close", summary="Закрыть опрос")
async def close_poll(
    poll_id: PollId,
    current_account: RequireConsentDep,
    polls_service: FromDishka[PollsService],
) -> PollCard:
    card = await polls_service.close(poll_id, current_account.user_id)
    return PollCard.of_card(card)
