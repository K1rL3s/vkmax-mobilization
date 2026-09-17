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
from zheka.core.enums import PollStatus
from zheka.core.ids import HouseId, PollId

router = APIRouter(tags=["Опросы"], route_class=DishkaRoute)


@router.get("/houses/{house_id}/polls", summary="Опросы дома")
async def list_polls(
    house_id: HouseId,
    residency: ResidencyForHouseDep,
    status: PollStatus | None = None,
) -> list[PollListItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post("/houses/{house_id}/polls", summary="Создать опрос дома")
async def create_poll(
    house_id: HouseId,
    residency: ResidencyForHouseDep,
    body: CreatePollRequest,
) -> PollCard:
    raise NotImplementedError("ещё не реализовано")


@router.get("/polls/{poll_id}", summary="Карточка опроса")
async def get_poll(
    poll_id: PollId,
    current_account: RequireConsentDep,
) -> PollCard:
    raise NotImplementedError("ещё не реализовано")


@router.post("/polls/{poll_id}/vote", summary="Проголосовать")
async def vote_in_poll(
    poll_id: PollId,
    current_account: RequireConsentDep,
    body: VoteRequest,
) -> PollResults:
    raise NotImplementedError("ещё не реализовано")


@router.get("/polls/{poll_id}/results", summary="Результаты и прогноз кворума")
async def get_poll_results(
    poll_id: PollId,
    current_account: RequireConsentDep,
) -> PollResults:
    raise NotImplementedError("ещё не реализовано")


@router.get("/polls/{poll_id}/non-voters", summary="Непроголосовавшие квартиры")
async def list_poll_non_voters(
    poll_id: PollId,
    current_account: RequireConsentDep,
) -> list[PollNonVoterItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post("/polls/{poll_id}/close", summary="Закрыть опрос")
async def close_poll(
    poll_id: PollId,
    current_account: RequireConsentDep,
) -> PollCard:
    raise NotImplementedError("ещё не реализовано")
