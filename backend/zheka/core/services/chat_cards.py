from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.enums import ChatCardKind, RequestCategory, RequestStatus
from zheka.core.ids import HouseId, RequestGroupId, RequestId
from zheka.core.services.request_groups import complaint_sources
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.requests import RequestsRepo

STATUS_ORDER = list(RequestStatus)


class ChatCardView(ZhekaType):
    house_id: HouseId
    text: str
    me_too: RequestCategory | None = None
    join: bool = False


class ChatCardsService:
    __slots__ = ("_houses", "_requests")

    def __init__(self, requests_repo: RequestsRepo, houses_repo: HousesRepo) -> None:
        self._requests = requests_repo
        self._houses = houses_repo

    async def render(self, kind: ChatCardKind, ref_id: int) -> ChatCardView | None:
        if kind is ChatCardKind.GROUP:
            return await self._group(RequestGroupId(ref_id))
        if kind is ChatCardKind.REQUEST:
            return await self._request(RequestId(ref_id))
        return None

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
