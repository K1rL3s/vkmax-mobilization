from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.enums import ChatCardKind, RequestCategory, RequestStatus
from zheka.core.ids import HouseId, RequestGroupId
from zheka.core.services.request_groups import complaint_sources
from zheka.infra.database.repos.requests import RequestsRepo

STATUS_ORDER = list(RequestStatus)


class ChatCardView(ZhekaType):
    house_id: HouseId
    text: str
    me_too: RequestCategory | None = None
    join: bool = False


class ChatCardsService:
    __slots__ = ("_requests",)

    def __init__(self, requests_repo: RequestsRepo) -> None:
        self._requests = requests_repo

    async def render(self, kind: ChatCardKind, ref_id: int) -> ChatCardView | None:
        if kind is ChatCardKind.GROUP:
            return await self._group(RequestGroupId(ref_id))
        return None

    async def _group(self, group_id: RequestGroupId) -> ChatCardView | None:
        group = await self._requests.get_group(group_id)
        members = await self._requests.list_for_group(group_id)
        if group is None or not members:
            return None
        flats = len(complaint_sources(members))
        status = min((member.status for member in members), key=STATUS_ORDER.index)
        if STATUS_ORDER.index(status) >= STATUS_ORDER.index(RequestStatus.ON_REVIEW):
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
