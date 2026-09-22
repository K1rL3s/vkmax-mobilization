from collections.abc import Sequence
from datetime import UTC, datetime

from zheka.base import ZhekaType
from zheka.core.enums import (
    ChatBinder,
    ChatStatus,
    EventType,
    ResidentStatus,
    UnpinMethod,
)
from zheka.core.errors import InvalidRequest, InvalidState, NotEnoughRights
from zheka.core.ids import HouseId, MaxChatId, UserId
from zheka.core.models import Chat, ChatPin, House
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
MAX_PINS = 15
PIN_TEXT_LIMIT = 100
PIN_DENIED = "🚫 Закреплять в этом чате могут председатель и сотрудники УК"
PIN_NEEDS_RIGHTS = "🛡 Чтобы закреплять сообщения, сделайте бота администратором чата"
PIN_HINT = "💡 Ответьте командой /pin на сообщение, которое нужно закрепить"
PINS_FULL = f"📌 В списке уже {MAX_PINS} закрепов. Открепите лишнее командой /unpin"
UNPIN_HINT = (
    "💡 Ответьте командой /unpin на закрепленное сообщение или укажите номер "
    "из списка, например /unpin 2"
)


class MessageRef(ZhekaType):
    mid: str
    seq: int


class PinList(ZhekaType):
    chat: Chat
    house_id: HouseId
    pins: Sequence[ChatPin]


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
        await self._chats.unpin(await self._chats.list_pins(chat_id), datetime.now(UTC))

    async def on_bot_removed(self, chat_id: MaxChatId) -> None:
        await self._chats.set_removed(chat_id)

    async def bind(
        self,
        user_id: UserId,
        chat_id: MaxChatId,
        house_id: HouseId,
    ) -> None:
        chat = await self._free_chat(chat_id)
        house = await self._houses.get(house_id)
        binder = None if house is None else await self._binder(user_id, house)
        if binder is None:
            raise NotEnoughRights("Привязать этот чат к дому вы не можете")
        await self._bind(chat, house_id, user_id, binder)

    async def bind_by_code(
        self,
        user_id: UserId,
        chat_id: MaxChatId,
        code: str,
    ) -> None:
        chat = await self._free_chat(chat_id)
        house = await self._houses.get_by_binding_code(code.strip().lower())
        if house is None:
            raise InvalidRequest(WRONG_CODE)
        await self._bind(chat, house.id, user_id, ChatBinder.CODE)

    async def set_admin(self, chat_id: MaxChatId, is_admin: bool) -> Chat:
        bound = await self._bound(chat_id)
        if bound is None:
            raise InvalidState(CHAT_NOT_BOUND)
        chat, house_id = bound
        granted = is_admin and not chat.bot_is_admin
        await self._chats.set_admin(chat, is_admin)
        if granted:
            await self._events.record(
                EventType.CHAT_ADMIN_GRANTED,
                user_id=chat.bound_by,
                chat_id=chat_id,
                house_id=house_id,
            )
            self._notifications.welcome_chat(chat_id, house_id)
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
        self,
        chat: Chat,
        house_id: HouseId,
        user_id: UserId,
        binder: ChatBinder,
    ) -> None:
        await self._chats.bind(chat, house_id, user_id)
        await self._events.record(
            EventType.CHAT_BOUND,
            user_id=user_id,
            chat_id=chat.chat_id,
            house_id=house_id,
            by_role=binder.value,
        )

    async def pin(
        self,
        user_id: UserId | None,
        chat_id: MaxChatId,
        target: MessageRef | None,
        text: str | None,
    ) -> None:
        bound = await self._bound(chat_id)
        if bound is None:
            return
        chat, house_id = bound
        author, binder = await self._pinner(user_id, chat, house_id)
        if target is None:
            raise InvalidRequest(PIN_HINT)
        text = (text or "").strip()[:PIN_TEXT_LIMIT] or None
        pins = await self._chats.list_pins(chat_id)
        listed = next((pin for pin in pins if pin.mid == target.mid), None)
        if listed is not None:
            await self._chats.set_pin_text(listed, text)
        elif len(pins) >= MAX_PINS:
            raise InvalidRequest(PINS_FULL)
        else:
            await self._chats.add_pin(
                ChatPin(
                    chat_id=chat_id,
                    mid=target.mid,
                    seq=target.seq,
                    text=text,
                    pinned_by=author,
                ),
            )
            await self._events.record(
                EventType.CHAT_PINNED,
                user_id=author,
                chat_id=chat_id,
                house_id=house_id,
                by_role=binder.value,
            )
        self._notifications.sync_chat_pins(chat_id)

    async def unpin(
        self,
        user_id: UserId | None,
        chat_id: MaxChatId,
        target: MessageRef | None,
        number: int | None,
    ) -> None:
        bound = await self._bound(chat_id)
        if bound is None:
            return
        chat, house_id = bound
        author, binder = await self._pinner(user_id, chat, house_id)
        pins = await self._chats.list_pins(chat_id)
        pin: ChatPin | None = None
        method = UnpinMethod.REPLY
        if target is not None:
            pin = next((listed for listed in pins if listed.mid == target.mid), None)
        elif number is not None and 1 <= number <= len(pins):
            pin, method = pins[number - 1], UnpinMethod.NUMBER
        if pin is None:
            raise InvalidRequest(UNPIN_HINT)
        await self._chats.unpin([pin], datetime.now(UTC))
        await self._events.record(
            EventType.CHAT_UNPINNED,
            user_id=author,
            chat_id=chat_id,
            house_id=house_id,
            method=method.value,
            by_role=binder.value,
        )
        self._notifications.sync_chat_pins(chat_id)

    async def on_message_removed(self, chat_id: MaxChatId, mid: str) -> None:
        chat = await self._chats.lock(chat_id)
        if chat is None or chat.pins_mid != mid:
            return
        pins = await self._chats.list_pins(chat_id)
        await self._chats.unpin(pins, datetime.now(UTC))
        await self._chats.set_pins_mid(chat, None)
        for _ in pins:
            await self._events.record(
                EventType.CHAT_UNPINNED,
                chat_id=chat_id,
                house_id=chat.house_id,
                method=UnpinMethod.LIST_DELETED.value,
            )

    async def pin_list(self, chat_id: MaxChatId) -> PinList | None:
        bound = await self._bound(chat_id)
        if bound is None:
            return None
        chat, house_id = bound
        return PinList(
            chat=chat,
            house_id=house_id,
            pins=await self._chats.list_pins(chat_id),
        )

    async def _bound(self, chat_id: MaxChatId) -> tuple[Chat, HouseId] | None:
        chat = await self._chats.lock(chat_id)
        if (
            chat is None
            or chat.house_id is None
            or chat.bound_at is None
            or chat.status != ChatStatus.ACTIVE
        ):
            return None
        return chat, chat.house_id

    async def _pinner(
        self,
        user_id: UserId | None,
        chat: Chat,
        house_id: HouseId,
    ) -> tuple[UserId, ChatBinder]:
        house = await self._houses.get(house_id)
        binder = (
            None
            if user_id is None or house is None
            else await self._binder(user_id, house)
        )
        if user_id is None or binder is None:
            raise NotEnoughRights(PIN_DENIED)
        if not chat.bot_is_admin:
            raise InvalidState(PIN_NEEDS_RIGHTS)
        return user_id, binder
