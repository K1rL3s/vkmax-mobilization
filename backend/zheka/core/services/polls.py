from collections.abc import Sequence
from datetime import UTC, datetime

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.enums import EventType, PollStatus, ResidentStatus
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    InvalidValue,
    NotEnoughRights,
)
from zheka.core.ids import (
    FlatId,
    HouseId,
    OrgId,
    PollId,
    PollOptionId,
    ResidentId,
    UserId,
)
from zheka.core.models import Flat, Poll, PollOption, PollVote, Resident
from zheka.core.roles import is_staff
from zheka.core.services.events import EventsService
from zheka.core.services.quorum import FlatArea, QuorumForecast, forecast
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

# дом столько квартир не наберет, чтобы постраничная выборка что-то отрезала,
# а прогноз кворума не имеет права потерять ни одну квартиру дома
_ALL_FLATS_LIMIT = 10_000
# минимум различных непустых вариантов ответа в опросе
MIN_POLL_OPTIONS = 2

POLL_NOT_FOUND = "Опрос не найден"
HOUSE_NOT_FOUND = "Дом не найден"
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
    my_option_ids: list[PollOptionId]
    voted: bool
    voted_flats: int


class PollOptionCount(ZhekaType):
    option: PollOption
    flats_count: int
    area: int  # 1/100 square metre


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
    # строку переводит в CLOSED задача close_expired_polls раз в сутки - до
    # нее сырой статус может врать, если ends_at уже прошел
    if poll.status is PollStatus.CLOSED or poll.ends_at <= now:
        return PollStatus.CLOSED
    return PollStatus.ACTIVE


def _is_open(poll: Poll, now: datetime) -> bool:
    return _effective_status(poll, now) is PollStatus.ACTIVE


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
    valid_ids = {PollOptionId(option.id) for option in options}
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
        now = datetime.now(UTC)
        if draft.ends_at <= now:
            raise InvalidValue(ENDS_IN_PAST)
        options = _clean_options(draft.options)

        if org_id is not None:
            # сотрудник УК - право уже подтвердил CurrentOrgDep, здесь только
            # проверка, что дом действительно этой организации
            house = await self._houses.get_for_org(house_id, org_id)
            if house is None:
                raise EntityNotFound(HOUSE_NOT_FOUND)
            role = "staff"
        else:
            resident = await self._residents.get_for_house(user_id, house_id)
            if resident is None:
                raise EntityNotFound(HOUSE_NOT_FOUND)
            if resident.status is ResidentStatus.BLOCKED:
                raise NotEnoughRights(texts.blocked_detail(resident.block_reason))
            if not resident.is_chairman:
                raise NotEnoughRights(NOT_A_CHAIRMAN)
            role = "chairman"

        poll = await self._polls.create(
            house_id,
            org_id,
            user_id,
            role,
            draft.title,
            draft.description,
            draft.is_multiple,
            now,
            draft.ends_at,
            options,
        )
        await self._events.record(
            EventType.POLL_CREATED,
            user_id=user_id,
            poll_id=PollId(poll.id),
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
        polls = await self._polls.list_for_house(house_id, None)
        now = datetime.now(UTC)
        items: list[PollListItemData] = []
        for poll in polls:
            effective = _effective_status(poll, now)
            if status is not None and effective is not status:
                continue
            items.append(await self._list_item(poll, user_id, effective))
        # стабильная сортировка дважды: сначала свежие сверху, потом активные
        # перед закрытыми - обе заметки блока 12 выполняются на одном списке.
        # id - надежный второй ключ: now() в PostgreSQL общий на транзакцию,
        # и два опроса, заведенных подряд в одной транзакции, получают
        # одинаковый created_at, а id все равно растет по порядку вставки
        items.sort(key=lambda item: (item.poll.created_at, item.poll.id), reverse=True)
        items.sort(key=lambda item: item.status is PollStatus.CLOSED)
        return items

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

        polls = await self._polls.list_for_org(org_id, house_id, None)
        now = datetime.now(UTC)
        dated = [(poll, _effective_status(poll, now)) for poll in polls]
        if status is not None:
            dated = [pair for pair in dated if pair[1] is status]
        dated.sort(key=lambda pair: (pair[0].created_at, pair[0].id), reverse=True)
        dated.sort(key=lambda pair: pair[1] is PollStatus.CLOSED)

        total = len(dated)
        page = dated[offset : offset + limit]
        houses = {
            HouseId(house.id): house
            for house in await self._houses.list_by_ids(
                {HouseId(poll.house_id) for poll, _status in page},
            )
        }

        result: list[AdminPollListItemData] = []
        for poll, effective in page:
            item = await self._list_item(poll, user_id, effective)
            house = houses.get(HouseId(poll.house_id))
            result.append(
                AdminPollListItemData(
                    item=item,
                    address="" if house is None else house.address,
                ),
            )
        return result, total

    async def vote(
        self,
        poll_id: PollId,
        user_id: UserId,
        option_ids: Sequence[PollOptionId],
    ) -> PollResultsData:
        poll = await self._get_poll(poll_id)
        resident = await self._residents.get_for_house(user_id, HouseId(poll.house_id))
        if resident is None:
            raise EntityNotFound(POLL_NOT_FOUND)

        now = datetime.now(UTC)
        if not _is_open(poll, now):
            raise InvalidState(POLL_ENDED)
        if resident.status is ResidentStatus.BLOCKED:
            raise NotEnoughRights(texts.blocked_detail(resident.block_reason))
        if not resident.can_vote:
            raise NotEnoughRights(TENANT_CANNOT_VOTE)

        options = await self._polls.list_options(PollId(poll.id))
        chosen = _validated_option_ids(poll, options, option_ids)

        existing = await self._polls.get_vote(PollId(poll.id), user_id)
        if existing:
            raise InvalidState(ALREADY_VOTED)

        counted_by_area = await self._counted_by_area(poll, resident)
        inserted = await self._polls.add_vote(
            PollId(poll.id),
            chosen,
            user_id,
            ResidentId(resident.id),
            FlatId(resident.flat_id) if resident.flat_id is not None else None,
            counted_by_area=counted_by_area,
        )
        if len(inserted) != len(chosen):
            # гонка: параллельный запрос вставил эти же строки первым
            raise InvalidState(ALREADY_VOTED)

        await self._events.record(
            EventType.POLL_VOTED,
            user_id=user_id,
            poll_id=PollId(poll.id),
        )
        return await self._results(poll)

    async def results(self, poll_id: PollId, user_id: UserId) -> PollResultsData:
        poll = await self._reachable_poll(poll_id, user_id)
        return await self._results(poll)

    async def non_voters(self, poll_id: PollId, user_id: UserId) -> list[Flat]:
        poll = await self._get_poll(poll_id)
        await self._require_initiator_or_staff(poll, user_id)

        voted_ids = set(
            await self._polls.voted_flat_ids(PollId(poll.id), verified_only=True),
        )
        flats = await self._house_flats(HouseId(poll.house_id))
        non_voters = [flat for flat in flats if FlatId(flat.id) not in voted_ids]
        non_voters.sort(
            key=lambda flat: (flat.entrance is None, flat.entrance or 0, flat.number),
        )
        return non_voters

    async def close(self, poll_id: PollId, user_id: UserId) -> PollCardData:
        poll = await self._get_poll(poll_id)
        await self._require_initiator_or_staff(poll, user_id)
        await self._polls.close(PollId(poll.id))
        return await self._card(poll, user_id)

    async def _card(self, poll: Poll, user_id: UserId) -> PollCardData:
        now = datetime.now(UTC)
        options = await self._polls.list_options(PollId(poll.id))
        votes = await self._polls.get_vote(PollId(poll.id), user_id)
        voted_flats = await self._voted_flats_count(PollId(poll.id))
        resident = await self._residents.get_for_house(user_id, HouseId(poll.house_id))
        can_vote = (
            resident is not None
            and resident.status is ResidentStatus.ACTIVE
            and resident.can_vote
            and _is_open(poll, now)
        )
        return PollCardData(
            poll=poll,
            status=_effective_status(poll, now),
            options=options,
            can_vote=can_vote,
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
        votes = await self._polls.get_vote(PollId(poll.id), user_id)
        voted_flats = await self._voted_flats_count(PollId(poll.id))
        return PollListItemData(
            poll=poll,
            status=status,
            voted=bool(votes),
            voted_flats=voted_flats,
        )

    async def _results(self, poll: Poll) -> PollResultsData:
        now = datetime.now(UTC)
        options = await self._polls.list_options(PollId(poll.id))
        votes = await self._polls.count_votes(PollId(poll.id))
        flats = await self._house_flats(HouseId(poll.house_id))
        areas_by_flat = {FlatId(flat.id): flat.area for flat in flats}
        flats_without_area = sum(1 for flat in flats if flat.area is None)

        weighted = [vote for vote in votes if vote.counted_by_area]
        voted_flat_ids = {
            FlatId(vote.flat_id) for vote in weighted if vote.flat_id is not None
        }
        voted = [
            FlatArea(flat_id=flat_id, area=areas_by_flat.get(flat_id))
            for flat_id in voted_flat_ids
        ]
        all_flats = [
            FlatArea(flat_id=FlatId(flat.id), area=flat.area) for flat in flats
        ]
        unverified_flats = len(
            {vote.user_id for vote in votes if not vote.counted_by_area},
        )
        poll_forecast = forecast(voted, all_flats, unverified_flats)

        option_counts = [
            self._option_count(option, weighted, areas_by_flat) for option in options
        ]
        return PollResultsData(
            poll=poll,
            status=_effective_status(poll, now),
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
            FlatId(vote.flat_id)
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
        weighted_flats = await self._polls.voted_flat_ids(
            PollId(poll.id),
            verified_only=True,
        )
        return FlatId(resident.flat_id) not in weighted_flats

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
        resident = await self._residents.get_for_house(user_id, HouseId(poll.house_id))
        if resident is not None:
            return poll
        if poll.org_id is not None and await self._is_org_staff(
            OrgId(poll.org_id),
            user_id,
        ):
            return poll
        raise EntityNotFound(POLL_NOT_FOUND)

    async def _require_initiator_or_staff(self, poll: Poll, user_id: UserId) -> None:
        if UserId(poll.created_by_user_id) == user_id:
            return
        if poll.org_id is not None and await self._is_org_staff(
            OrgId(poll.org_id),
            user_id,
        ):
            return
        raise NotEnoughRights(NOT_INITIATOR)

    async def _is_org_staff(self, org_id: OrgId, user_id: UserId) -> bool:
        member = await self._orgs.get_member(org_id, user_id)
        return member is not None and is_staff(member.role)
