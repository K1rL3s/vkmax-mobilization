from collections.abc import Sequence
from datetime import UTC, datetime

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.enums import EventType, PollStatus, ResidentStatus
from zheka.core.errors import (
    HOUSE_NOT_FOUND,
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    InvalidValue,
    NotEnoughRights,
)
from zheka.core.ids import FlatId, HouseId, OrgId, PollId, PollOptionId, UserId
from zheka.core.models import Flat, Poll, PollOption, PollVote, Resident
from zheka.core.roles import is_staff
from zheka.core.services.events import EventsService
from zheka.core.services.quorum import QuorumForecast, forecast
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

_ALL_FLATS_LIMIT = 10_000
MIN_POLL_OPTIONS = 2

POLL_NOT_FOUND = "Опрос не найден"
NOT_A_CHAIRMAN = "Опрос дома может создать только председатель"
POLL_ENDED = "Опрос завершен"
TENANT_CANNOT_VOTE = "Арендатор не участвует в опросах"
ALREADY_VOTED = "Вы уже проголосовали"
EMPTY_VOTE = "Выберите хотя бы один вариант ответа"
UNKNOWN_OPTION = "Вариант не относится к этому опросу"
SINGLE_CHOICE_ONLY = "В этом опросе можно выбрать только один вариант"
NEED_TWO_OPTIONS = "Добавьте минимум два разных варианта ответа"
ENDS_IN_PAST = "Дата окончания опроса должна быть в будущем"
NOT_INITIATOR = "Доступно только организатору опроса"


class PollDraft(ZhekaType):
    title: str
    description: str | None
    options: Sequence[str]
    ends_at: datetime
    is_multiple: bool = False


class PollListItemData(ZhekaType):
    poll: Poll
    status: PollStatus
    voted: bool
    voted_flats: int


class PollCardData(ZhekaType):
    poll: Poll
    status: PollStatus
    options: Sequence[PollOption]
    can_vote: bool
    can_manage: bool
    my_option_ids: list[PollOptionId]
    voted: bool
    voted_flats: int


class PollOptionCount(ZhekaType):
    option: PollOption
    flats_count: int
    area: int


class PollResultsData(ZhekaType):
    poll: Poll
    status: PollStatus
    forecast: QuorumForecast
    options: list[PollOptionCount]
    flats_without_area: int


class AdminPollListItemData(ZhekaType):
    item: PollListItemData
    address: str


def _effective_status(poll: Poll, now: datetime) -> PollStatus:
    if poll.status is PollStatus.CLOSED or poll.ends_at <= now:
        return PollStatus.CLOSED
    return PollStatus.ACTIVE


def _clean_options(options: Sequence[str]) -> list[str]:
    cleaned = [text.strip() for text in options if text.strip()]
    if len(cleaned) < MIN_POLL_OPTIONS or len(set(cleaned)) != len(cleaned):
        raise InvalidRequest(NEED_TWO_OPTIONS)
    return cleaned


def _validated_option_ids(
    poll: Poll,
    options: Sequence[PollOption],
    option_ids: Sequence[PollOptionId],
) -> list[PollOptionId]:
    if not option_ids:
        raise InvalidRequest(EMPTY_VOTE)
    valid_ids = {option.id for option in options}
    chosen = list(dict.fromkeys(option_ids))
    if any(option_id not in valid_ids for option_id in chosen):
        raise InvalidRequest(UNKNOWN_OPTION)
    if not poll.is_multiple and len(chosen) > 1:
        raise InvalidRequest(SINGLE_CHOICE_ONLY)
    return chosen


class PollsService:
    __slots__ = ("_events", "_houses", "_orgs", "_polls", "_residents")

    def __init__(
        self,
        polls_repo: PollsRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        orgs_repo: OrgsRepo,
        events_service: EventsService,
    ) -> None:
        self._polls = polls_repo
        self._houses = houses_repo
        self._residents = residents_repo
        self._orgs = orgs_repo
        self._events = events_service

    async def create(
        self,
        user_id: UserId,
        house_id: HouseId,
        draft: PollDraft,
        *,
        org_id: OrgId | None,
    ) -> PollCardData:
        options = _clean_options(draft.options)

        if org_id is not None:
            house = await self._houses.get_for_org(house_id, org_id)
            if house is None:
                raise EntityNotFound(HOUSE_NOT_FOUND)
            role = "staff"
        else:
            house = await self._houses.get(house_id)
            resident = await self._residents.get_for_house(user_id, house_id)
            if house is None or resident is None:
                raise EntityNotFound(HOUSE_NOT_FOUND)
            if resident.status is ResidentStatus.BLOCKED:
                raise NotEnoughRights(texts.blocked_detail(resident.block_reason))
            if not resident.is_chairman:
                raise NotEnoughRights(NOT_A_CHAIRMAN)
            role = "chairman"
            org_id = house.org_id

        now = datetime.now(UTC)
        ends_at = house.to_utc(draft.ends_at)
        if ends_at <= now:
            raise InvalidValue(ENDS_IN_PAST)
        poll = await self._polls.create(
            house_id,
            org_id,
            user_id,
            role,
            draft.title,
            draft.description,
            draft.is_multiple,
            now,
            ends_at,
            options,
        )
        await self._events.record(
            EventType.POLL_CREATED,
            user_id=user_id,
            poll_id=poll.id,
            by_role=role,
        )
        return await self._card(poll, user_id)

    async def get_card(self, poll_id: PollId, user_id: UserId) -> PollCardData:
        poll = await self._reachable_poll(poll_id, user_id)
        return await self._card(poll, user_id)

    async def list_polls(
        self,
        house_id: HouseId,
        user_id: UserId,
        status: PollStatus | None,
    ) -> list[PollListItemData]:
        polls = await self._polls.list_for_house(house_id)
        return [
            await self._list_item(poll, user_id, effective)
            for poll, effective in _by_status(polls, status)
        ]

    async def list_org_polls(
        self,
        org_id: OrgId,
        user_id: UserId,
        house_id: HouseId | None,
        status: PollStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminPollListItemData], int]:
        if house_id is not None:
            house = await self._houses.get_for_org(house_id, org_id)
            if house is None:
                raise EntityNotFound(HOUSE_NOT_FOUND)

        dated = _by_status(await self._polls.list_for_org(org_id, house_id), status)
        total = len(dated)
        page = dated[offset : offset + limit]
        houses = {
            house.id: house
            for house in await self._houses.list_by_ids(
                {poll.house_id for poll, _status in page},
            )
        }

        result = [
            AdminPollListItemData(
                item=await self._list_item(poll, user_id, effective),
                address=houses[poll.house_id].address,
            )
            for poll, effective in page
        ]
        return result, total

    async def vote(
        self,
        poll_id: PollId,
        user_id: UserId,
        option_ids: Sequence[PollOptionId],
    ) -> PollResultsData:
        poll = await self._get_poll(poll_id)
        resident = await self._residents.get_for_house(user_id, poll.house_id)
        if resident is None:
            raise EntityNotFound(POLL_NOT_FOUND)

        if _effective_status(poll, datetime.now(UTC)) is PollStatus.CLOSED:
            raise InvalidState(POLL_ENDED)
        if resident.status is ResidentStatus.BLOCKED:
            raise NotEnoughRights(texts.blocked_detail(resident.block_reason))
        if not resident.can_vote:
            raise NotEnoughRights(TENANT_CANNOT_VOTE)

        options = await self._polls.list_options(poll.id)
        chosen = _validated_option_ids(poll, options, option_ids)

        existing = await self._polls.get_vote(poll.id, user_id)
        if existing:
            raise InvalidState(ALREADY_VOTED)

        counted_by_area = await self._counted_by_area(poll, resident)
        inserted = await self._polls.add_vote(
            poll.id,
            chosen,
            user_id,
            resident.id,
            resident.flat_id,
            counted_by_area=counted_by_area,
        )
        if len(inserted) != len(chosen):
            raise InvalidState(ALREADY_VOTED)

        await self._events.record(
            EventType.POLL_VOTED,
            user_id=user_id,
            poll_id=poll.id,
        )
        return await self._results(poll)

    async def results(self, poll_id: PollId, user_id: UserId) -> PollResultsData:
        poll = await self._reachable_poll(poll_id, user_id)
        return await self._results(poll)

    async def non_voters(self, poll_id: PollId, user_id: UserId) -> list[Flat]:
        poll = await self._get_poll(poll_id)
        await self._require_initiator_or_staff(poll, user_id)

        voted_ids = set(await self._polls.voted_flat_ids(poll.id, verified_only=True))
        flats = await self._house_flats(poll.house_id)
        non_voters = [flat for flat in flats if flat.id not in voted_ids]
        non_voters.sort(
            key=lambda flat: (flat.entrance is None, flat.entrance or 0, flat.number),
        )
        return non_voters

    async def close(self, poll_id: PollId, user_id: UserId) -> PollCardData:
        poll = await self._get_poll(poll_id)
        await self._require_initiator_or_staff(poll, user_id)
        await self._polls.close(poll)
        return await self._card(poll, user_id)

    async def _card(self, poll: Poll, user_id: UserId) -> PollCardData:
        status = _effective_status(poll, datetime.now(UTC))
        options = await self._polls.list_options(poll.id)
        votes = await self._polls.get_vote(poll.id, user_id)
        voted_flats = await self._voted_flats_count(poll.id)
        resident = await self._residents.get_for_house(user_id, poll.house_id)
        can_vote = (
            resident is not None
            and resident.status is ResidentStatus.ACTIVE
            and resident.can_vote
            and status is PollStatus.ACTIVE
        )
        return PollCardData(
            poll=poll,
            status=status,
            options=options,
            can_vote=can_vote,
            can_manage=await self._can_manage(poll, user_id),
            my_option_ids=[PollOptionId(vote.option_id) for vote in votes],
            voted=bool(votes),
            voted_flats=voted_flats,
        )

    async def _list_item(
        self,
        poll: Poll,
        user_id: UserId,
        status: PollStatus,
    ) -> PollListItemData:
        votes = await self._polls.get_vote(poll.id, user_id)
        voted_flats = await self._voted_flats_count(poll.id)
        return PollListItemData(
            poll=poll,
            status=status,
            voted=bool(votes),
            voted_flats=voted_flats,
        )

    async def _results(self, poll: Poll) -> PollResultsData:
        options = await self._polls.list_options(poll.id)
        votes = await self._polls.count_votes(poll.id)
        flats = await self._house_flats(poll.house_id)
        areas_by_flat = {flat.id: flat.area for flat in flats}
        flats_without_area = sum(1 for flat in flats if flat.area is None)

        weighted = [vote for vote in votes if vote.counted_by_area]
        voted_flat_ids = {vote.flat_id for vote in weighted if vote.flat_id is not None}
        unverified_flats = len(
            {vote.user_id for vote in votes if not vote.counted_by_area},
        )
        poll_forecast = forecast(
            [areas_by_flat.get(flat_id) for flat_id in voted_flat_ids],
            list(areas_by_flat.values()),
            unverified_flats,
        )

        option_counts = [
            self._option_count(option, weighted, areas_by_flat) for option in options
        ]
        return PollResultsData(
            poll=poll,
            status=_effective_status(poll, datetime.now(UTC)),
            forecast=poll_forecast,
            options=option_counts,
            flats_without_area=flats_without_area,
        )

    @staticmethod
    def _option_count(
        option: PollOption,
        weighted_votes: Sequence[PollVote],
        areas_by_flat: dict[FlatId, int | None],
    ) -> PollOptionCount:
        flat_ids = {
            vote.flat_id
            for vote in weighted_votes
            if vote.option_id == option.id and vote.flat_id is not None
        }
        area = sum(
            area
            for flat_id in flat_ids
            if (area := areas_by_flat.get(flat_id)) is not None
        )
        return PollOptionCount(option=option, flats_count=len(flat_ids), area=area)

    async def _counted_by_area(self, poll: Poll, resident: Resident) -> bool:
        if resident.verified_at is None or resident.flat_id is None:
            return False
        weighted_flats = await self._polls.voted_flat_ids(poll.id, verified_only=True)
        return resident.flat_id not in weighted_flats

    async def _voted_flats_count(self, poll_id: PollId) -> int:
        return len(await self._polls.voted_flat_ids(poll_id, verified_only=True))

    async def _house_flats(self, house_id: HouseId) -> Sequence[Flat]:
        flats, _total = await self._houses.list_flats(
            house_id,
            None,
            None,
            limit=_ALL_FLATS_LIMIT,
            offset=0,
        )
        return flats

    async def _get_poll(self, poll_id: PollId) -> Poll:
        poll = await self._polls.get(poll_id)
        if poll is None:
            raise EntityNotFound(POLL_NOT_FOUND)
        return poll

    async def _reachable_poll(self, poll_id: PollId, user_id: UserId) -> Poll:
        poll = await self._get_poll(poll_id)
        resident = await self._residents.get_for_house(user_id, poll.house_id)
        if resident is None and not await self._is_poll_staff(poll, user_id):
            raise EntityNotFound(POLL_NOT_FOUND)
        return poll

    async def _can_manage(self, poll: Poll, user_id: UserId) -> bool:
        if poll.created_by_user_id == user_id:
            return True
        return await self._is_poll_staff(poll, user_id)

    async def _require_initiator_or_staff(self, poll: Poll, user_id: UserId) -> None:
        if not await self._can_manage(poll, user_id):
            raise NotEnoughRights(NOT_INITIATOR)

    async def _is_poll_staff(self, poll: Poll, user_id: UserId) -> bool:
        if poll.org_id is None:
            return False
        member = await self._orgs.get_member(poll.org_id, user_id)
        return member is not None and is_staff(member.role)


def _by_status(
    polls: Sequence[Poll],
    status: PollStatus | None,
) -> list[tuple[Poll, PollStatus]]:
    now = datetime.now(UTC)
    dated = [(poll, _effective_status(poll, now)) for poll in polls]
    if status is not None:
        dated = [pair for pair in dated if pair[1] is status]
    dated.sort(key=lambda pair: (pair[0].created_at, pair[0].id), reverse=True)
    dated.sort(key=lambda pair: pair[1] is PollStatus.CLOSED)
    return dated
