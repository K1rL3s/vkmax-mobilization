from collections.abc import Sequence
from datetime import UTC, datetime

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.deeplinks import poll_app_path
from zheka.core.enums import ChatCardKind, PollStatus, RequestCategory, RequestStatus
from zheka.core.ids import HouseId, PollId, RequestGroupId, RequestId
from zheka.core.services.polls import PollsService
from zheka.core.services.quorum import area_percent_of
from zheka.core.services.request_groups import complaint_sources
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.requests import RequestsRepo

STATUS_ORDER = list(RequestStatus)


class CardVote(ZhekaType):
    text: str
    poll_id: PollId
    option_id: int


class ChatCardView(ZhekaType):
    house_id: HouseId
    text: str
    me_too: RequestCategory | None = None
    votes: Sequence[CardVote] = ()
    app_path: str | None = None
    join: bool = False


class ChatCardsService:
    __slots__ = ("_houses", "_polls", "_requests")

    def __init__(
        self,
        requests_repo: RequestsRepo,
        houses_repo: HousesRepo,
        polls_service: PollsService,
    ) -> None:
        self._requests = requests_repo
        self._houses = houses_repo
        self._polls = polls_service

    async def render(self, kind: ChatCardKind, ref_id: int) -> ChatCardView | None:
        if kind is ChatCardKind.GROUP:
            return await self._group(RequestGroupId(ref_id))
        if kind is ChatCardKind.REQUEST:
            return await self._request(RequestId(ref_id))
        return await self._poll(PollId(ref_id))

    async def _poll(self, poll_id: PollId) -> ChatCardView | None:
        data = await self._polls.chat_card(poll_id)
        if data is None:
            return None
        results, house = data.results, data.house
        poll = results.poll
        active = poll.effective_status(datetime.now(UTC)) is PollStatus.ACTIVE
        rows = [
            texts.PollCardRow(
                text=count.option.text,
                flats=count.flats_count,
                percent=area_percent_of(count.area, data.total_area),
            )
            for count in results.options
        ]
        text = texts.poll_card(
            poll.title,
            poll.created_by_role,
            rows,
            data.voted_flats,
            data.total_flats,
            house.local(poll.ends_at) if active else None,
        )
        votes = [
            CardVote(
                text=texts.vote_button(number, count.option.text),
                poll_id=poll.id,
                option_id=count.option.id,
            )
            for number, count in enumerate(results.options, start=1)
        ]
        return ChatCardView(
            house_id=house.id,
            text=text,
            votes=votes if active and not poll.is_multiple else (),
            app_path=poll_app_path(poll.id) if active and poll.is_multiple else None,
            join=True,
        )

    async def _request(self, request_id: RequestId) -> ChatCardView | None:
        request = await self._requests.get(request_id)
        house = None if request is None else await self._houses.get(request.house_id)
        if request is None or house is None:
            return None
        if request.group_id is not None:
            text = texts.request_card_grouped(request.id, request.category)
            return ChatCardView(house_id=house.id, text=text)
        if _reviewed(request.status):
            text = texts.request_card_done(request.id)
            return ChatCardView(house_id=house.id, text=text)
        return ChatCardView(
            house_id=house.id,
            text=texts.request_card(request, house),
            me_too=request.category,
            join=True,
        )

    async def _group(self, group_id: RequestGroupId) -> ChatCardView | None:
        group = await self._requests.get_group(group_id)
        members = await self._requests.list_for_group(group_id)
        if group is None or not members:
            return None
        flats = len(complaint_sources(members))
        status = min((member.status for member in members), key=STATUS_ORDER.index)
        if _reviewed(status):
            return ChatCardView(
                house_id=group.house_id,
                text=texts.group_card_done(group.category, flats),
            )
        return ChatCardView(
            house_id=group.house_id,
            text=texts.group_card(group.category, flats, status),
            me_too=group.category,
            join=True,
        )


def _reviewed(status: RequestStatus) -> bool:
    return STATUS_ORDER.index(status) >= STATUS_ORDER.index(RequestStatus.ON_REVIEW)
