from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import (
    IdempotencyDep,
    RequireConsentDep,
    ResidencyForHouseDep,
)
from zheka.api.schemas.proposals import (
    AnswerProposalRequest,
    CreateProposalRequest,
    MyProposalsResponse,
    ProposalItem,
)
from zheka.core.ids import CouncilProposalId, HouseId
from zheka.core.services.proposals import ProposalsService

router = APIRouter(tags=["Предложения совету дома"], route_class=DishkaRoute)


@router.post("/houses/{house_id}/proposals", summary="Предложить совету дома")
async def create_proposal(
    house_id: HouseId,
    residency: ResidencyForHouseDep,
    body: CreateProposalRequest,
    proposals_service: FromDishka[ProposalsService],
    idempotency: IdempotencyDep,
) -> ProposalItem:
    saved = await idempotency.replay(ProposalItem)
    if saved is not None:
        return saved
    view = await proposals_service.propose(residency.user_id, house_id, body.text)
    response = ProposalItem.of(view)
    await idempotency.save(response)
    return response


@router.get("/houses/{house_id}/proposals/my", summary="Мои предложения")
async def list_my_proposals(
    house_id: HouseId,
    residency: ResidencyForHouseDep,
    proposals_service: FromDishka[ProposalsService],
) -> MyProposalsResponse:
    view = await proposals_service.list_mine(residency.user_id, house_id)
    return MyProposalsResponse.of(view)


@router.get("/houses/{house_id}/proposals", summary="Предложения дома")
async def list_house_proposals(
    house_id: HouseId,
    residency: ResidencyForHouseDep,
    proposals_service: FromDishka[ProposalsService],
) -> list[ProposalItem]:
    views = await proposals_service.list_for_chairman(residency.user_id, house_id)
    return [ProposalItem.of(view) for view in views]


@router.post("/proposals/{proposal_id}/answer", summary="Ответить на предложение")
async def answer_proposal(
    proposal_id: CouncilProposalId,
    current_account: RequireConsentDep,
    body: AnswerProposalRequest,
    proposals_service: FromDishka[ProposalsService],
) -> ProposalItem:
    view = await proposals_service.answer(
        proposal_id,
        current_account.user_id,
        body.answer,
        body.poll_id,
        accepted=body.accepted,
    )
    return ProposalItem.of(view)
