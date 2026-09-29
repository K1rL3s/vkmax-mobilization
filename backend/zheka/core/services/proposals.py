from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.deeplinks import MEETINGS_APP_PATH
from zheka.core.enums import (
    EventType,
    NotificationCategory,
    ProposalStatus,
    ResidentStatus,
)
from zheka.core.errors import (
    HOUSE_NOT_FOUND,
    EntityNotFound,
    InvalidState,
    InvalidValue,
    NotEnoughRights,
)
from zheka.core.ids import CouncilProposalId, HouseId, PollId, UserId
from zheka.core.models import CouncilProposal, Resident
from zheka.core.services.events import EventsService
from zheka.core.services.notifications import NotificationsService
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.proposals import ProposalsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

TEXT_MIN = 10
TEXT_MAX = 1000
PER_DAY = 3

PROPOSAL_NOT_FOUND = "Предложение не найдено"
NO_CHAIRMAN = "В доме пока нет председателя совета"
NOT_A_CHAIRMAN = "Предложения совету дома читает председатель"
BAD_LENGTH = f"Предложение должно быть от {TEXT_MIN} до {TEXT_MAX} символов"
TOO_MANY = f"Больше {PER_DAY} предложений в сутки отправить нельзя"
ALREADY_ANSWERED = "На это предложение уже ответили"
DECLINE_NEEDS_ANSWER = "Объясните автору, почему предложение отклонено"
POLL_WITHOUT_ACCEPT = "На опрос выносится только принятое предложение"
POLL_NOT_OF_HOUSE = "Опрос не найден"


class ProposalView(ZhekaType):
    id: CouncilProposalId
    created_at: datetime
    text: str
    status: ProposalStatus
    answer: str | None
    answered_at: datetime | None
    poll_id: PollId | None


class MyProposals(ZhekaType):
    has_chairman: bool
    items: Sequence[ProposalView]


class ProposalsService:
    __slots__ = (
        "_events",
        "_notifications",
        "_polls",
        "_proposals",
        "_residents",
    )

    def __init__(
        self,
        proposals_repo: ProposalsRepo,
        residents_repo: ResidentsRepo,
        polls_repo: PollsRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> None:
        self._proposals = proposals_repo
        self._residents = residents_repo
        self._polls = polls_repo
        self._notifications = notifications_service
        self._events = events_service

    async def propose(
        self,
        user_id: UserId,
        house_id: HouseId,
        text: str,
    ) -> ProposalView:
        await self._resident(user_id, house_id)
        text = text.strip()
        if not TEXT_MIN <= len(text) <= TEXT_MAX:
            raise InvalidValue(BAD_LENGTH)
        chairman = await self._chairman(house_id)
        if chairman is None:
            raise InvalidState(NO_CHAIRMAN)
        now = datetime.now(UTC)
        sent = await self._proposals.count_since(
            house_id,
            user_id,
            now - timedelta(days=1),
        )
        if sent >= PER_DAY:
            raise InvalidState(TOO_MANY)
        proposal = await self._proposals.create(house_id, user_id, text)
        await self._events.record(
            EventType.PROPOSAL_SENT,
            user_id=user_id,
            proposal_id=proposal.id,
            house_id=house_id,
        )
        self._notifications.notify_user(
            chairman.user_id,
            texts.proposal_for_chairman(text),
            category=NotificationCategory.REQUESTS,
            mandatory=False,
            app_button=texts.OPEN_APP,
            app_path=MEETINGS_APP_PATH,
        )
        return _view(proposal)

    async def list_mine(self, user_id: UserId, house_id: HouseId) -> MyProposals:
        await self._resident(user_id, house_id)
        proposals = await self._proposals.list_for_author(house_id, user_id)
        return MyProposals(
            has_chairman=await self._chairman(house_id) is not None,
            items=[_view(proposal) for proposal in proposals],
        )

    async def list_for_chairman(
        self,
        user_id: UserId,
        house_id: HouseId,
    ) -> Sequence[ProposalView]:
        await self._acting_chairman(user_id, house_id)
        proposals = await self._proposals.list_for_house(house_id)
        return [_view(proposal) for proposal in proposals]

    async def answer(
        self,
        proposal_id: CouncilProposalId,
        user_id: UserId,
        answer: str | None,
        poll_id: PollId | None,
        *,
        accepted: bool,
    ) -> ProposalView:
        proposal = await self._proposals.get(proposal_id)
        if proposal is None:
            raise EntityNotFound(PROPOSAL_NOT_FOUND)
        await self._acting_chairman(user_id, proposal.house_id)
        if proposal.status is not ProposalStatus.NEW:
            raise InvalidState(ALREADY_ANSWERED)
        answer = None if answer is None else answer.strip() or None
        if answer is None and not accepted:
            raise InvalidValue(DECLINE_NEEDS_ANSWER)
        if answer is not None and len(answer) > TEXT_MAX:
            raise InvalidValue(BAD_LENGTH)
        await self._check_poll(poll_id, proposal, accepted=accepted)
        status = ProposalStatus.ACCEPTED if accepted else ProposalStatus.DECLINED
        now = datetime.now(UTC)
        answered = await self._proposals.answer(proposal, status, answer, poll_id, now)
        await self._events.record(
            EventType.PROPOSAL_ANSWERED,
            user_id=user_id,
            proposal_id=answered.id,
            status=status.value,
        )
        self._notifications.notify_user(
            answered.author_user_id,
            texts.proposal_answered(answered.text, answer, accepted=accepted),
            category=NotificationCategory.REQUESTS,
            mandatory=True,
            app_button=texts.OPEN_APP,
            app_path=MEETINGS_APP_PATH,
        )
        return _view(answered)

    async def _check_poll(
        self,
        poll_id: PollId | None,
        proposal: CouncilProposal,
        *,
        accepted: bool,
    ) -> None:
        if poll_id is None:
            return
        if not accepted:
            raise InvalidValue(POLL_WITHOUT_ACCEPT)
        poll = await self._polls.get(poll_id)
        if poll is None or poll.house_id != proposal.house_id:
            raise EntityNotFound(POLL_NOT_OF_HOUSE)

    async def _chairman(self, house_id: HouseId) -> Resident | None:
        chairman = await self._residents.get_chairman(house_id)
        if chairman is None or chairman.status is not ResidentStatus.ACTIVE:
            return None
        return chairman

    async def _resident(self, user_id: UserId, house_id: HouseId) -> Resident:
        resident = await self._residents.get_for_house(user_id, house_id)
        if resident is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        if resident.status is ResidentStatus.BLOCKED:
            raise NotEnoughRights(texts.blocked_detail(resident.block_reason))
        return resident

    async def _acting_chairman(self, user_id: UserId, house_id: HouseId) -> Resident:
        resident = await self._resident(user_id, house_id)
        if not resident.is_chairman:
            raise NotEnoughRights(NOT_A_CHAIRMAN)
        return resident


def _view(proposal: CouncilProposal) -> ProposalView:
    return ProposalView(
        id=proposal.id,
        created_at=proposal.created_at,
        text=proposal.text,
        status=proposal.status,
        answer=proposal.answer,
        answered_at=proposal.answered_at,
        poll_id=proposal.poll_id,
    )
