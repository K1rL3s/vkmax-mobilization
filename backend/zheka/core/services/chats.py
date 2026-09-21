from zheka.core.enums import ChatBinder, ChatStatus, EventType, ResidentStatus
from zheka.core.errors import InvalidRequest, InvalidState, NotEnoughRights
from zheka.core.ids import HouseId, MaxChatId, UserId
from zheka.core.models import Chat, House
from zheka.core.roles import is_staff
from zheka.core.services.events import EventsService
from zheka.core.services.notifications import NotificationsService
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

CHAT_TAKEN = "Этот чат уже привязан или бота из него удалили"
WRONG_CODE = "Код не подошел. Проверьте его на карточке дома и пришлите еще раз"
CHAT_NOT_BOUND = "Чат больше не привязан к дому"


class ChatsService:
    __slots__ = (
        "_chats",
        "_events",
        "_houses",
        "_notifications",
        "_orgs",
        "_residents",
    )

    def __init__(
        self,
        chats_repo: ChatsRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        residents_repo: ResidentsRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> None:
        self._chats = chats_repo
        self._houses = houses_repo
        self._orgs = orgs_repo
        self._residents = residents_repo
        self._notifications = notifications_service
        self._events = events_service

    async def bindable_houses(self, user_id: UserId) -> list[House]:
        houses: list[House] = []
        for member in await self._orgs.list_for_user(user_id):
            if is_staff(member.role):
                houses.extend(await self._houses.list_for_org(member.org_id))
        known = {house.id for house in houses}
        chaired = [
            resident.house_id
            for resident in await self._residents.list_for_user(user_id)
            if resident.is_chairman
            and resident.status is ResidentStatus.ACTIVE
            and resident.house_id not in known
        ]
        houses.extend(await self._houses.list_by_ids(chaired))
        return houses

    async def is_resident(self, user_id: UserId) -> bool:
        residents = await self._residents.list_for_user(user_id)
        return any(r.status is ResidentStatus.ACTIVE for r in residents)

    async def on_bot_added(self, chat_id: MaxChatId, title: str) -> None:
        await self._chats.upsert_added(chat_id, title)

    async def on_bot_removed(self, chat_id: MaxChatId) -> None:
        await self._chats.set_removed(chat_id)

    async def bind(
        self, user_id: UserId, chat_id: MaxChatId, house_id: HouseId
    ) -> None:
        chat = await self._free_chat(chat_id)
        house = await self._houses.get(house_id)
        binder = None if house is None else await self._binder(user_id, house)
        if binder is None:
            raise NotEnoughRights("Привязать этот чат к дому вы не можете")
        await self._bind(chat, house_id, user_id, binder)

    async def bind_by_code(
        self, user_id: UserId, chat_id: MaxChatId, code: str
    ) -> None:
        chat = await self._free_chat(chat_id)
        house = await self._houses.get_by_binding_code(code.strip().lower())
        if house is None:
            raise InvalidRequest(WRONG_CODE)
        await self._bind(chat, house.id, user_id, ChatBinder.CODE)

    async def set_admin(self, chat_id: MaxChatId, is_admin: bool) -> Chat:
        chat = await self._chats.get(chat_id)
        if (
            chat is None
            or chat.house_id is None
            or chat.bound_at is None
            or chat.status != ChatStatus.ACTIVE
        ):
            raise InvalidState(CHAT_NOT_BOUND)
        granted = is_admin and not chat.bot_is_admin
        await self._chats.set_admin(chat, is_admin)
        if granted:
            await self._events.record(
                EventType.CHAT_ADMIN_GRANTED,
                user_id=chat.bound_by,
                chat_id=chat_id,
                house_id=chat.house_id,
            )
            self._notifications.welcome_chat(chat_id, chat.house_id)
        return chat

    async def _free_chat(self, chat_id: MaxChatId) -> Chat:
        chat = await self._chats.get(chat_id)
        if (
            chat is None
            or chat.status != ChatStatus.ACTIVE
            or chat.bound_at is not None
        ):
            raise NotEnoughRights(CHAT_TAKEN)
        return chat

    async def _binder(self, user_id: UserId, house: House) -> ChatBinder | None:
        if house.org_id is not None:
            member = await self._orgs.get_member(house.org_id, user_id)
            if member is not None and is_staff(member.role):
                return ChatBinder.STAFF
        resident = await self._residents.get_for_house(user_id, house.id)
        if (
            resident is not None
            and resident.is_chairman
            and resident.status is ResidentStatus.ACTIVE
        ):
            return ChatBinder.CHAIRMAN
        return None

    async def _bind(
        self, chat: Chat, house_id: HouseId, user_id: UserId, binder: ChatBinder
    ) -> None:
        await self._chats.bind(chat, house_id, user_id)
        await self._events.record(
            EventType.CHAT_BOUND,
            user_id=user_id,
            chat_id=chat.chat_id,
            house_id=house_id,
            by_role=binder.value,
        )
