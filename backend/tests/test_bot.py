import asyncio
import json
import re
import secrets
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from html import escape
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from dishka import AsyncContainer
from maxo import Router
from maxo.dialogs import BgManagerFactory, ShowMode, StartMode
from maxo.dialogs.api.entities import NewMessage
from maxo.dialogs.context.media_storage import MediaIdStorage
from maxo.dialogs.test_tools import BotClient, MockMessageManager
from maxo.dialogs.test_tools.bot_client import FakeBot
from maxo.dialogs.test_tools.keyboard import InlineButtonTextLocator
from maxo.enums import ChatStatus as MaxChatStatus, ChatType, MessageLinkType
from maxo.errors import MaxBotForbiddenError, MaxBotNotFoundError
from maxo.omit import Omittable, Omitted
from maxo.routing.filters import Command
from maxo.routing.signals import MaxoUpdate
from maxo.types import (
    BotAddedToChat,
    BotRemovedFromChat,
    BotStarted,
    BotStopped,
    DialogMuted,
    DialogUnmuted,
    GetPinnedMessageResult,
    LocationAttachment,
    Message,
    MessageBody,
    MessageCreated,
    MessageRemoved,
    NewMessageLink,
    OpenAppButton,
    PhotoAttachment,
    PhotoAttachmentPayload,
    Recipient,
    RequestGeoLocationButton,
    SendMessageResult,
)
from maxo.types.chat import Chat as MaxChat
from maxo.types.link_button import LinkButton
from maxo.types.simple_query_result import SimpleQueryResult
from maxo.utils.deeplink import create_start_link
from maxo.utils.link import id_to_message_url
from maxo.utils.payload import decode_payload
from sqlalchemy import Row, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import InMemoryBroker

from tests.conftest import PROBE_ROUTERS, RecordingBroker

from zheka.bot import BotSetup
from zheka.bot.handlers.access.handlers import PICKED
from zheka.bot.handlers.access.windows import GONE_TEXT
from zheka.bot.handlers.chats.handlers import BOUND_TEXT, NO_RIGHTS_YET
from zheka.bot.handlers.chats.router import PINNED, UNPINNED
from zheka.bot.handlers.chats.windows import CODE_TEXT, HOUSE_TEXT, RIGHTS_TEXT
from zheka.bot.handlers.commands.deeplinks import (
    DEMO_ADMIN_NOTICE,
    DEMO_RESIDENT_NOTICE,
    DEMO_STAFF_NOTICE,
    ORG_JOINED,
)
from zheka.bot.handlers.consent.windows import GIVEN_TEXT
from zheka.bot.handlers.executor.handlers import PHOTO_TAKEN
from zheka.bot.handlers.executor.windows import HANDED_OVER_TEXT, RESULT_PHOTO_TEXT
from zheka.bot.handlers.menu.windows import MENU_TEXT
from zheka.bot.handlers.onboarding.handlers import HOUSE_LINKED
from zheka.bot.handlers.onboarding.windows import (
    CITY_TEXT,
    FLAT_LIST_TEXT,
    FLAT_NUMBER_TEXT,
    HOUSE_TEXT as SEARCH_HOUSE_TEXT,
    METHOD_TEXT,
    MISSED_TEXT,
    NEARBY_TEXT,
    STREET_TEXT,
)
from zheka.bot.handlers.requests.windows import (
    CATEGORY_TEXT,
    CONFIRM_TEXT,
    DESCRIPTION_TEXT,
    NOT_CONNECTED_TEXT,
    PHOTO_TEXT,
)
from zheka.bot.handlers.review.handlers import repeat_sent
from zheka.bot.handlers.review.windows import ASK_TEXT, RATED_TEXT, REJECTION_TEXT
from zheka.bot.message_manager import ZhekaMessageManager
from zheka.bot.states import Consent, Menu
from zheka.broker.task_names import TaskName
from zheka.broker.tasks.chats import (
    JOIN_HOUSE,
    PINS_HERE,
    on_bot_added,
    sync_chat_pins,
    welcome_chat,
)
from zheka.broker.tasks.notifications import broadcast_to_chats
from zheka.broker.tasks.reminders import broadcast_access_request
from zheka.broker.tasks.requests import (
    attach_result_photo,
    send_executor_card,
    send_review_card,
)
from zheka.core.consent import CONSENT_TEXT, CONSENT_VERSION
from zheka.core.deeplinks import (
    DeeplinkKind,
    entrance_qr_payload,
    house_payload,
    org_invite_payload,
)
from zheka.core.enums import (
    CATEGORY_RULES,
    ChatStatus,
    EventSource,
    EventType,
    OrgRole,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestStatus,
    ResidentRole,
    ResidentStatus,
)
from zheka.core.errors import INVITE_NOT_FOUND, NotEnoughRights
from zheka.core.ids import (
    AccessRequestId,
    AccessSlotId,
    FlatId,
    HouseId,
    MaxChatId,
    MaxUserId,
    OrgId,
    RequestId,
    UserId,
)
from zheka.core.models import User
from zheka.core.services.access import SLOT_FULL
from zheka.core.services.chats import (
    CHAT_NOT_BOUND,
    CHAT_TAKEN,
    PINS_TITLE,
    UNPIN_HINT,
    WRONG_CODE,
)
from zheka.core.services.demo import DEMO_INNS, NOT_SEEDED, demo_flat_number
from zheka.core.services.requests import MAX_RATING, MIN_RATING, REJECT_NOT_ON_REVIEW
from zheka.core.texts import REQUEST_STATUS_LABELS
from zheka.infra.database.models import (
    Chat,
    ChatPin,
    Flat,
    House,
    OrgInvite,
    OrgMember,
    Organization,
    Request,
    Resident,
)
from zheka.infra.database.repos.access import AccessRepo
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.access import access_targets_table
from zheka.infra.database.tables.chats import chats_table
from zheka.infra.database.tables.events import events_table
from zheka.infra.database.tables.houses import houses_table
from zheka.infra.database.tables.organizations import org_members_table
from zheka.infra.database.tables.requests import requests_table
from zheka.infra.database.tables.residents import residents_table
from zheka.infra.database.tables.users import users_table
from zheka.infra.max import MaxSender
from zheka.infra.max.sender import _chat_rate_limit, dialog_notify, is_chat_admin


class _RecordingBot(FakeBot):
    def __init__(self) -> None:
        super().__init__()
        self.notifies: list[bool] = []
        self.texts: list[str | None] = []
        self.chat_ids: list[Any] = []
        self.user_ids: list[Any] = []
        self.links: list[Any] = []

    async def send_message(  # type: ignore[mutable-override]
        self,
        *_: Any,
        **kwargs: Any,
    ) -> SendMessageResult:
        self.notifies.append(kwargs["notify"])
        self.texts.append(kwargs.get("text"))
        self.chat_ids.append(kwargs.get("chat_id"))
        self.user_ids.append(kwargs.get("user_id"))
        self.links.append(kwargs.get("link"))
        return SendMessageResult(
            message=Message(
                recipient=Recipient(chat_type=ChatType.DIALOG, chat_id=1),
                timestamp=datetime.now(UTC),
                body=MessageBody(mid="1", seq=1, text=kwargs.get("text")),
            ),
        )


def _new_message() -> NewMessage:
    return NewMessage(
        recipient=Recipient(chat_type=ChatType.DIALOG, chat_id=1),
        text="Окно",
    )


ACCEPT = InlineButtonTextLocator("✅ Даю согласие")
NEW_REQUEST = InlineButtonTextLocator("📝 Подать заявку")
FIRST_CATEGORY = InlineButtonTextLocator(
    CATEGORY_RULES[next(iter(RequestCategory))].caption,
)
NEXT = InlineButtonTextLocator("➡️ Дальше")
SEND = InlineButtonTextLocator("📨 Отправить")
TO_MENU = InlineButtonTextLocator("🏠 Меню")


def _max_id() -> MaxUserId:
    return MaxUserId(secrets.randbits(40))


@pytest.fixture
def client(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    message_manager: MockMessageManager,
) -> BotClient:
    message_manager.reset_history()
    max_user_id = _max_id()
    return BotClient(
        bot_setup.dp,
        user_id=max_user_id,
        chat_id=max_user_id,
        bot=fake_bot,
    )


async def _saved(session: AsyncSession, max_user_id: MaxUserId) -> User | None:
    return await UsersRepo(session).get_by_max_id(max_user_id)


async def test_consent_button_writes_the_consent_and_opens_the_menu(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    fake_bot: FakeBot,
) -> None:
    await client.send("/start")

    await client.click(message_manager.last_message(), ACCEPT)

    user = await _saved(bot_session, MaxUserId(client.user.id))
    assert user is not None
    assert user.consent_at is not None
    assert user.consent_version is not None
    keyboard = message_manager.last_message().body.keyboard
    assert keyboard is not None
    buttons = [button for row in keyboard.buttons for button in row]
    assert [
        button.web_app for button in buttons if isinstance(button, OpenAppButton)
    ] == [fake_bot.state.info.username]


async def test_a_message_from_a_house_chat_starts_nothing(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    message_manager: MockMessageManager,
) -> None:
    message_manager.reset_history()
    max_user_id = _max_id()
    group = BotClient(
        bot_setup.dp,
        user_id=max_user_id,
        chat_id=max_user_id,
        chat_type=ChatType.CHAT,
        bot=fake_bot,
    )

    await group.send("/start")

    assert message_manager.sent_messages == []


async def test_a_mini_app_upsert_keeps_the_chat_id_and_the_stop_mark(
    session: AsyncSession,
) -> None:
    repo = UsersRepo(session)
    max_user_id = _max_id()
    await repo.upsert_by_max_id(max_user_id, "Житель", None, MaxChatId(777))
    await repo.set_bot_stopped(max_user_id, datetime.now(UTC))

    user = await repo.upsert_by_max_id(max_user_id, "Житель", None, None)

    assert user.max_chat_id == MaxChatId(777)
    assert user.bot_stopped_at is not None


class _NotifyProbe:
    def __init__(self) -> None:
        self.notify: bool | None = None

    def bg(self, **_: Any) -> Any:
        return self

    @asynccontextmanager
    async def fg(self) -> AsyncIterator[Any]:
        yield self

    async def start(self, *_: Any, **__: Any) -> None:
        self.notify = dialog_notify.get()


@pytest.mark.parametrize("notify", [True, False])
async def test_start_dialog_carries_the_sound_into_the_window(
    fake_bot: FakeBot,
    notify: bool,
) -> None:
    probe = _NotifyProbe()
    sender = MaxSender(fake_bot, cast(BgManagerFactory, probe))
    user = User(id=UserId(1), max_user_id=_max_id(), name="Житель")
    user.max_chat_id = MaxChatId(42)

    await sender.start_dialog(Menu.main, user, notify=notify)

    assert probe.notify is notify
    assert dialog_notify.get() is False


@pytest.mark.parametrize("stopped", [False, True])
async def test_a_user_without_a_live_private_chat_gets_no_window(
    fake_bot: FakeBot,
    stopped: bool,
) -> None:
    probe = _NotifyProbe()
    sender = MaxSender(fake_bot, cast(BgManagerFactory, probe))
    user = User(id=UserId(1), max_user_id=_max_id(), name="Житель")
    if stopped:
        user.max_chat_id = MaxChatId(42)
        user.bot_stopped_at = datetime.now(UTC)

    await sender.start_dialog(Menu.main, user, notify=False)

    assert probe.notify is None


async def test_the_dialog_message_is_silent_unless_the_task_asked_for_sound() -> None:
    recorder = _RecordingBot()
    manager = ZhekaMessageManager(media_id_storage=MediaIdStorage())

    await manager.send_message(recorder, _new_message())
    assert recorder.notifies == [False]

    token = dialog_notify.set(True)
    try:
        await manager.send_message(recorder, _new_message())
    finally:
        dialog_notify.reset(token)
    assert recorder.notifies == [False, True]


async def test_start_dialog_returns_with_the_window_already_sent(
    client: BotClient,
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await client.send("/start")
    user = await _saved(bot_session, MaxUserId(client.user.id))
    assert user is not None
    message_manager.reset_history()
    sender = MaxSender(fake_bot, bot_setup.bg_manager_factory)

    await sender.start_dialog(Menu.main, user, notify=False)

    assert message_manager.sent_messages != []


async def test_a_window_opened_by_a_task_keeps_the_user_name(
    client: BotClient,
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    bot_session: AsyncSession,
) -> None:
    await client.send("/start")
    max_user_id = MaxUserId(client.user.id)
    user = await _saved(bot_session, max_user_id)
    assert user is not None
    name = user.name
    sender = MaxSender(fake_bot, bot_setup.bg_manager_factory)

    await sender.start_dialog(Menu.main, user, notify=False)

    bot_session.expire_all()
    fresh = await _saved(bot_session, max_user_id)
    assert fresh is not None
    assert fresh.name == name


async def test_a_tap_on_a_dead_window_restarts_the_menu(
    client: BotClient,
    message_manager: MockMessageManager,
) -> None:
    await client.send("/start")
    stale = message_manager.last_message()
    await client.send("/start")
    message_manager.reset_history()

    await client.click(stale, ACCEPT)

    assert MENU_TEXT in (message_manager.last_message().body.text or "")


async def test_the_start_is_recorded_once_and_a_loose_message_is_not_a_start(
    client: BotClient,
    bot_session: AsyncSession,
) -> None:
    await client.send("здравствуйте")
    await client.send("/start")

    events = await _starts_of(bot_session, client)

    assert len(events) == 1
    assert events[0].payload == {"source": "direct"}


async def test_a_tap_from_a_house_chat_renders_nothing(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    message_manager: MockMessageManager,
) -> None:
    max_user_id = _max_id()
    manager = bot_setup.bg_manager_factory.bg(
        bot=fake_bot,
        user_id=max_user_id,
        chat_id=max_user_id,
        chat_type=ChatType.CHAT,
    )
    async with manager.fg() as dialog_manager:
        await dialog_manager.start(Consent.ask, mode=StartMode.RESET_STACK)
    window = message_manager.last_message()
    message_manager.reset_history()
    group = BotClient(
        bot_setup.dp,
        user_id=max_user_id,
        chat_id=max_user_id,
        chat_type=ChatType.CHAT,
        bot=fake_bot,
    )

    await group.click(window, ACCEPT)

    assert message_manager.sent_messages == []


ERROR_PROBE_COMMAND = "errorprobe"
PROBE_DENIED = "Пробная доменная ошибка"

error_probe_router = Router(name="error-probe")
PROBE_ROUTERS.append(error_probe_router)


@error_probe_router.message_created(Command(ERROR_PROBE_COMMAND))
async def error_probe_handler(_update: MessageCreated) -> None:
    raise NotEnoughRights(PROBE_DENIED)


async def test_a_domain_error_on_a_message_is_answered(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
) -> None:
    recorder = _RecordingBot()
    outside = BotClient(
        bot_setup.dp,
        user_id=_max_id(),
        chat_id=_max_id(),
        chat_type=ChatType.CHAT,
        bot=recorder,
    )

    await outside.send(f"/{ERROR_PROBE_COMMAND}")

    assert recorder.texts == [PROBE_DENIED]


async def test_a_window_shares_the_chat_bucket_with_a_broadcast(
    fake_bot: FakeBot,
) -> None:
    probe = _NotifyProbe()
    sender = MaxSender(fake_bot, cast(BgManagerFactory, probe))
    user = User(id=UserId(1), max_user_id=_max_id(), name="Житель")
    user.max_chat_id = MaxChatId(_max_id())
    bucket = _chat_rate_limit(user.max_user_id)

    async with bucket, bucket:
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.1):
                await sender.start_dialog(Menu.main, user, notify=False)

    assert probe.notify is None


async def _bot_started(client: BotClient, payload: Omittable[str | None]) -> None:
    await _feed(
        client,
        BotStarted(
            chat_id=client.chat.chat_id,
            user=client.user,
            payload=payload,
            timestamp=datetime.now(UTC),
        ),
    )


async def _bot_house(
    session: AsyncSession,
    *,
    city: str = "Тестоград",
    street: str = "Диплинковая",
    building: str | None = None,
    lat: Decimal | None = None,
    lon: Decimal | None = None,
) -> tuple[HouseId, str]:
    house = House(
        timezone="Europe/Moscow",
        region="Тестовая область",
        city=city,
        street=street,
        building=building or secrets.token_hex(2),
        cadastral_no=secrets.token_hex(8),
        chat_binding_code=secrets.token_hex(4),
        lat=lat,
        lon=lon,
    )
    session.add(house)
    await session.commit()
    await session.refresh(house)
    return house.id, house.address


async def _starts_of(session: AsyncSession, client: BotClient) -> Sequence[Row[Any]]:
    stmt = select(events_table).where(
        events_table.c.type == EventType.BOT_START,
        events_table.c.user_id.in_(
            select(users_table.c.id).where(users_table.c.max_user_id == client.user.id),
        ),
    )
    return (await session.execute(stmt)).all()


@pytest.mark.parametrize(
    "payload",
    ["не-диплинк", "demo_admin_9", "demo_staff", Omitted()],
)
async def test_a_start_without_a_deeplink_falls_through_to_start(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    payload: Omittable[str | None],
) -> None:
    await _bot_started(client, payload)

    assert message_manager.sent_messages
    assert CONSENT_TEXT in (message_manager.last_message().body.text or "")
    events = await _starts_of(bot_session, client)
    assert len(events) == 1
    assert events[0].payload == {"source": EventSource.DIRECT.value}


async def test_a_house_deeplink_asks_consent_and_then_opens_the_house(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    house_id, address = await _bot_house(bot_session)

    await _bot_started(client, house_payload(house_id))
    assert CONSENT_TEXT in (message_manager.last_message().body.text or "")

    await client.click(message_manager.last_message(), ACCEPT)

    text = message_manager.last_message().body.text or ""
    assert address in text
    assert MENU_TEXT not in text


async def test_a_dead_invite_link_is_answered_instead_of_silence(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    message_manager: MockMessageManager,
) -> None:
    message_manager.reset_history()
    max_user_id = _max_id()
    recorder = _RecordingBot()
    client = BotClient(
        bot_setup.dp,
        user_id=max_user_id,
        chat_id=max_user_id,
        bot=recorder,
    )
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    recorder.texts.clear()

    await _bot_started(client, org_invite_payload("deadbeef"))

    assert recorder.texts == [INVITE_NOT_FOUND]


async def _linked(
    session: AsyncSession,
    client: BotClient,
    house_id: HouseId,
    created_at: datetime,
) -> None:
    user = await _saved(session, MaxUserId(client.user.id))
    assert user is not None
    session.add(
        Resident(
            user_id=user.id,
            house_id=house_id,
            role=ResidentRole.OWNER,
            created_at=created_at,
        ),
    )
    await session.commit()


async def _draft_request(client: BotClient, message_manager: MockMessageManager) -> str:
    await client.click(message_manager.last_message(), NEW_REQUEST)
    address = message_manager.last_message().body.text or ""
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.send("Течет кран на кухне")
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)
    return address


async def test_the_request_goes_to_the_house_the_resident_linked_last(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    now = datetime.now(UTC)
    _, first = await _org_house(bot_session)
    _, last = await _org_house(bot_session)
    await _linked(bot_session, client, first, now)
    await _linked(bot_session, client, last, now + timedelta(minutes=1))
    last_house = await HousesRepo(bot_session).get(last)
    assert last_house is not None

    address = await _draft_request(client, message_manager)

    assert last_house.address in address
    enqueued = bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)
    assert enqueued[-1]["house_id"] == int(last)
    await client.click(message_manager.last_message(), TO_MENU)
    assert MENU_TEXT in (message_manager.last_message().body.text or "")


DEPART = InlineButtonTextLocator("🚗 Выехал")
READY = InlineButtonTextLocator("🏁 Готово")
RIGHTS_DONE = InlineButtonTextLocator("✅ Готово")
REJECT = InlineButtonTextLocator("👎 Сделано плохо")
RESULT_URL = "https://max.ru/result.jpg"
PHOTO_TOKEN = "photo-token"  # noqa: S105


async def _org_house(session: AsyncSession) -> tuple[OrgId, HouseId]:
    org = Organization(
        timezone="Europe/Moscow",
        name=f"УК {secrets.token_hex(4)}",
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Тестовая область, Тестоград, Тестовая, 1",
        registered_at=datetime.now(UTC),
    )
    session.add(org)
    await session.flush()
    house = House(
        timezone="Europe/Moscow",
        org_id=org.id,
        region="Тестовая область",
        city="Тестоград",
        street="Исполнительская",
        building=secrets.token_hex(2),
        cadastral_no=secrets.token_hex(8),
        chat_binding_code=secrets.token_hex(4),
    )
    session.add(house)
    await session.flush()
    ids = org.id, house.id
    await session.commit()
    return ids


async def _started(session: AsyncSession, client: BotClient) -> UserId:
    await client.send("/start")
    user = await _saved(session, MaxUserId(client.user.id))
    assert user is not None
    return user.id


async def _request(
    session: AsyncSession,
    house_id: HouseId,
    status: RequestStatus,
    *,
    author: UserId | None = None,
    executor: UserId | None = None,
) -> RequestId:
    request = Request(
        house_id=house_id,
        author_user_id=author,
        executor_user_id=executor,
        category=RequestCategory.LEAK,
        description="Течет кран",
        status=status,
        channel=RequestChannel.MINIAPP,
        reviewed_at=datetime.now(UTC) if status is RequestStatus.ON_REVIEW else None,
    )
    session.add(request)
    await session.flush()
    request_id = request.id
    await session.commit()
    return request_id


async def _executor_on(
    session: AsyncSession,
    client: BotClient,
    status: RequestStatus,
) -> RequestId:
    user_id = await _started(session, client)
    org_id, house_id = await _org_house(session)
    session.add(OrgMember(org_id=org_id, user_id=user_id, role=OrgRole.EXECUTOR))
    await session.commit()
    return await _request(session, house_id, status, executor=user_id)


async def _run(broker: InMemoryBroker, task: Any, **kwargs: Any) -> None:
    sent = await task.kicker().with_broker(broker).kiq(**kwargs)
    result = await sent.wait_result(timeout=5)
    assert not result.is_err, result.error


async def _status(session: AsyncSession, request_id: RequestId) -> Request:
    session.expire_all()
    request = await RequestsRepo(session).get(request_id)
    assert request is not None
    return request


async def _send_photo(client: BotClient) -> None:
    body = MessageBody(
        mid=secrets.token_hex(4),
        seq=1,
        text=None,
        attachments=[
            PhotoAttachment(
                payload=PhotoAttachmentPayload(
                    photo_id=1,
                    token=PHOTO_TOKEN,
                    url=RESULT_URL,
                ),
            ),
        ],
    )
    message = Message(
        sender=client.user,
        recipient=Recipient(chat_type=ChatType.DIALOG, chat_id=client.chat.chat_id),
        timestamp=datetime.now(UTC),
        body=body,
    )
    await _feed(client, MessageCreated(message=message, timestamp=datetime.now(UTC)))


async def _rendered(message_manager: MockMessageManager, text: str) -> None:
    async with asyncio.timeout(5):
        while not message_manager.sent_messages or text not in (  # noqa: ASYNC110
            message_manager.last_message().body.text or ""
        ):
            await asyncio.sleep(0.01)


Show = tuple[ShowMode, str | None, int | None, bool]


@pytest.fixture
def shows(
    message_manager: MockMessageManager,
    monkeypatch: pytest.MonkeyPatch,
) -> list[Show]:
    recorded: list[Show] = []
    original = message_manager.show_message

    async def recording(bot: Any, new_message: Any, old_message: Any) -> Any:
        recorded.append(
            (
                new_message.show_mode,
                new_message.text,
                new_message.recipient.chat_id,
                dialog_notify.get(),
            ),
        )
        return await original(bot, new_message, old_message)

    monkeypatch.setattr(message_manager, "show_message", recording)
    return recorded


def _shown(shows: list[Show], text: str) -> Show:
    return next(show for show in shows if text in (show[1] or ""))


async def test_a_tap_on_the_executor_card_moves_the_request(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    shows: list[Show],
) -> None:
    request_id = await _executor_on(bot_session, client, RequestStatus.ACCEPTED)

    await _run(task_broker, send_executor_card, request_id=request_id)
    await _run(task_broker, send_executor_card, request_id=request_id)
    await client.click(message_manager.last_message(), DEPART)

    cards = [mode for mode, text, *_ in shows if f"№{request_id}:" in (text or "")]
    assert cards[:2] == [ShowMode.SEND, ShowMode.SEND]
    assert (await _status(bot_session, request_id)).status is RequestStatus.IN_PROGRESS


async def test_ready_asks_for_the_photo_where_a_message_reaches_it(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    shows: list[Show],
    notices: _RecordingBot,
) -> None:
    request_id = await _executor_on(bot_session, client, RequestStatus.IN_PROGRESS)
    request = await _status(bot_session, request_id)
    await _run(task_broker, send_executor_card, request_id=request_id)
    await client.click(message_manager.last_message(), READY)
    await _rendered(message_manager, RESULT_PHOTO_TEXT)
    assert _shown(shows, RESULT_PHOTO_TEXT)[0] is ShowMode.SEND

    await _send_photo(client)

    assert bot_broker.enqueued(TaskName.ATTACH_RESULT_PHOTO)[-1] == {
        "user_id": request.executor_user_id,
        "request_id": request_id,
        "photo_urls": [RESULT_URL],
    }
    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert PHOTO_TAKEN in notices.texts


async def test_a_rejection_on_the_review_card_opens_a_repeat_from_the_bot(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    shows: list[Show],
    notices: _RecordingBot,
) -> None:
    request_id = await _reviewing(bot_session, client, task_broker)
    mode, _, chat_id, _ = shows[-1]
    assert mode is ShowMode.SEND
    assert chat_id == client.chat.chat_id

    await client.click(message_manager.last_message(), REJECT)
    await _rendered(message_manager, REJECTION_TEXT)
    await client.send("Кран все еще течет")

    parent = await _status(bot_session, request_id)
    assert parent.completion_reason is RequestCompletionReason.RESIDENT_REJECTED
    stmt = select(Request).where(requests_table.c.parent_request_id == request_id)
    repeat = (await bot_session.execute(stmt)).scalar_one()
    assert repeat.channel is RequestChannel.BOT
    assert repeat.description == "Кран все еще течет"
    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert repeat_sent(repeat.id) in notices.texts


ACCEPT_WORK = InlineButtonTextLocator("👍 Принять")
TOP_RATING = InlineButtonTextLocator(f"{MAX_RATING}️⃣")


async def _reviewing(
    session: AsyncSession,
    client: BotClient,
    broker: InMemoryBroker,
) -> RequestId:
    author = await _started(session, client)
    _, house_id = await _org_house(session)
    session.add(Resident(user_id=author, house_id=house_id, role=ResidentRole.OWNER))
    await session.commit()
    request_id = await _request(
        session,
        house_id,
        RequestStatus.ON_REVIEW,
        author=author,
    )
    await _run(broker, send_review_card, request_id=request_id)
    return request_id


async def _repeats_of(session: AsyncSession, request_id: RequestId) -> list[Request]:
    stmt = select(Request).where(requests_table.c.parent_request_id == request_id)
    return list((await session.execute(stmt)).scalars().all())


async def test_a_stale_rejection_prompt_files_no_repeat(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    request_id = await _reviewing(bot_session, client, task_broker)
    card = message_manager.last_message()
    await client.click(card, REJECT)
    await _rendered(message_manager, REJECTION_TEXT)
    await client.click(card, ACCEPT_WORK)

    await client.send("Спасибо, все хорошо")

    assert await _repeats_of(bot_session, request_id) == []
    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert REJECT_NOT_ON_REVIEW in notices.texts


async def test_a_tap_on_a_card_that_is_no_longer_his_shows_the_handover(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    request_id = await _executor_on(bot_session, client, RequestStatus.ACCEPTED)
    await _run(task_broker, send_executor_card, request_id=request_id)
    card = message_manager.last_message()
    stmt = delete(org_members_table).where(
        org_members_table.c.user_id == await _started(bot_session, client),
    )
    await bot_session.execute(stmt)
    await bot_session.commit()

    await client.click(card, DEPART)

    assert HANDED_OVER_TEXT.format(request_id=request_id) in (
        message_manager.last_message().body.text or ""
    )


async def test_a_tap_on_a_review_closed_elsewhere_renders_the_closed_request(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    request_id = await _reviewing(bot_session, client, task_broker)
    card = message_manager.last_message()
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(
            status=RequestStatus.DONE,
            completion_reason=RequestCompletionReason.AUTO_CLOSED,
        )
    )
    await bot_session.execute(stmt)
    await bot_session.commit()
    message_manager.reset_history()

    await client.click(card, ACCEPT_WORK)

    text = message_manager.last_message().body.text or ""
    assert REQUEST_STATUS_LABELS[RequestStatus.DONE] in text
    assert ASK_TEXT not in text


async def test_a_second_rating_renders_the_card_with_the_first(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    request_id = await _reviewing(bot_session, client, task_broker)
    await client.click(message_manager.last_message(), ACCEPT_WORK)
    rating = message_manager.last_message()
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(rating=MIN_RATING)
    )
    await bot_session.execute(stmt)
    await bot_session.commit()

    await client.click(rating, TOP_RATING)

    assert RATED_TEXT.format(rating=MIN_RATING) in (
        message_manager.last_message().body.text or ""
    )


async def test_a_refused_photo_rerenders_the_card_for_the_sender(
    client: BotClient,
    task_broker: InMemoryBroker,
    bot_broker: RecordingBroker,
    bot_session: AsyncSession,
    shows: list[Show],
) -> None:
    request_id = await _executor_on(bot_session, client, RequestStatus.IN_PROGRESS)
    sender_id = await _started(bot_session, client)
    other = User(max_user_id=_max_id(), name="Другой исполнитель")
    bot_session.add(other)
    await bot_session.flush()
    other_id = other.id
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(executor_user_id=other_id)
    )
    await bot_session.execute(stmt)
    await bot_session.commit()

    await _run(
        task_broker,
        attach_result_photo,
        user_id=sender_id,
        request_id=request_id,
        photo_urls=[],
    )

    enqueued = bot_broker.enqueued(TaskName.SEND_EXECUTOR_CARD)[-1]
    assert enqueued == {"request_id": request_id, "user_id": sender_id}
    await _run(task_broker, send_executor_card, **enqueued)
    _, text, chat_id, _ = shows[-1]
    assert HANDED_OVER_TEXT.format(request_id=request_id) in (text or "")
    assert chat_id == client.chat.chat_id
    assert (await _status(bot_session, request_id)).status is (
        RequestStatus.IN_PROGRESS
    )


async def _bot_stopped(client: BotClient) -> None:
    await _feed(
        client,
        BotStopped(
            chat_id=client.chat.chat_id,
            user=client.user,
            timestamp=datetime.now(UTC),
        ),
    )


async def test_a_private_update_after_a_stop_revives_the_bot(
    client: BotClient,
    bot_session: AsyncSession,
) -> None:
    await client.send("/start")
    max_user_id = MaxUserId(client.user.id)
    await _bot_stopped(client)
    stopped = await _saved(bot_session, max_user_id)
    assert stopped is not None
    assert stopped.bot_stopped_at is not None

    await client.send("/start")

    bot_session.expire_all()
    revived = await _saved(bot_session, max_user_id)
    assert revived is not None
    assert revived.bot_stopped_at is None


class _ChatApi:
    def __init__(self) -> None:
        self.left: list[int] = []
        self.is_admin = False

    async def leave_chat(self, *, chat_id: int, **_: Any) -> SimpleQueryResult:
        self.left.append(chat_id)
        return SimpleQueryResult(success=True)

    async def get_chat(self, *, chat_id: int, **_: Any) -> MaxChat:
        return MaxChat(
            chat_id=chat_id,
            type=ChatType.CHAT,
            status=MaxChatStatus.ACTIVE,
            last_event_time=datetime.now(UTC),
            is_public=False,
            participants_count=3,
            title=CHAT_TITLE,
        )

    async def get_membership(self, *, chat_id: int, **_: Any) -> Any:  # noqa: ARG002
        return type("Membership", (), {"is_admin": self.is_admin})()


CHAT_TITLE = "Соседи"


@pytest.fixture
def chat_api(fake_bot: FakeBot, monkeypatch: pytest.MonkeyPatch) -> _ChatApi:
    api = _ChatApi()
    for name in ("leave_chat", "get_chat", "get_membership"):
        monkeypatch.setattr(fake_bot, name, getattr(api, name))
    return api


def _chat_id() -> MaxChatId:
    return MaxChatId(-secrets.randbits(40))


async def _added_by(broker: InMemoryBroker, chat_id: MaxChatId, **kwargs: Any) -> None:
    await _run(broker, on_bot_added, chat_id=chat_id, **{"is_channel": False, **kwargs})


async def test_the_bot_leaves_a_chat_added_by_a_stranger(
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
) -> None:
    chat_id = _chat_id()

    await _added_by(task_broker, chat_id, initiator_max_user_id=_max_id())

    assert chat_api.left == [chat_id]
    assert await ChatsRepo(bot_session).get(chat_id) is None


async def _staff(session: AsyncSession, client: BotClient) -> HouseId:
    user_id = await _started(session, client)
    org_id, house_id = await _org_house(session)
    session.add(OrgMember(org_id=org_id, user_id=user_id, role=OrgRole.ADMIN))
    await session.commit()
    return house_id


async def test_the_bot_leaves_a_channel(
    client: BotClient,
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
) -> None:
    await _staff(bot_session, client)
    chat_id = _chat_id()

    await _added_by(
        task_broker,
        chat_id,
        is_channel=True,
        initiator_max_user_id=client.user.id,
    )

    assert chat_api.left == [chat_id]


async def test_the_bot_leaves_when_it_cannot_reach_the_initiator(
    client: BotClient,
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
) -> None:
    await _staff(bot_session, client)
    await _bot_stopped(client)
    chat_id = _chat_id()

    await _added_by(task_broker, chat_id, initiator_max_user_id=client.user.id)

    assert chat_api.left == [chat_id]


async def test_the_bot_leaves_when_the_initiator_never_started_it(
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
) -> None:
    max_user_id = _max_id()
    user = User(max_user_id=max_user_id, name="Из мини-аппа")
    bot_session.add(user)
    await bot_session.flush()
    user_id = user.id
    org_id, _ = await _org_house(bot_session)
    bot_session.add(OrgMember(org_id=org_id, user_id=user_id, role=OrgRole.ADMIN))
    await bot_session.commit()
    chat_id = _chat_id()

    await _added_by(task_broker, chat_id, initiator_max_user_id=max_user_id)

    assert chat_api.left == [chat_id]


async def test_staff_binds_the_chat_by_one_tap_and_the_welcome_follows(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    shows: list[Show],
) -> None:
    house_id = await _staff(bot_session, client)
    house = await HousesRepo(bot_session).get(house_id)
    assert house is not None
    chat_id = _chat_id()

    await _added_by(task_broker, chat_id, initiator_max_user_id=client.user.id)
    window = message_manager.last_message()
    assert HOUSE_TEXT.format(title=CHAT_TITLE) in (window.body.text or "")
    assert _shown(shows, HOUSE_TEXT.format(title=CHAT_TITLE))[0] is ShowMode.SEND
    house_button = InlineButtonTextLocator(re.escape(f"🏢 {house.address}"))
    await client.click(window, house_button)
    await client.click(message_manager.last_message(), RIGHTS_DONE)
    assert NO_RIGHTS_YET in (message_manager.last_message().body.text or "")
    chat_api.is_admin = True
    await client.click(message_manager.last_message(), RIGHTS_DONE)

    text = message_manager.last_message().body.text or ""
    assert BOUND_TEXT.format(title=CHAT_TITLE) in text
    assert MENU_TEXT not in text
    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None
    assert chat.house_id == house_id
    assert chat.bot_is_admin is True
    assert bot_broker.enqueued(TaskName.WELCOME_CHAT)[-1] == {
        "chat_id": chat_id,
        "house_id": house_id,
    }
    assert chat_api.left == []


async def test_a_resident_binds_the_chat_by_code(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
    shows: list[Show],
    notices: _RecordingBot,
) -> None:
    user_id = await _started(bot_session, client)
    _, house_id = await _org_house(bot_session)
    bot_session.add(
        Resident(user_id=user_id, house_id=house_id, role=ResidentRole.OWNER),
    )
    await bot_session.commit()
    house = await HousesRepo(bot_session).get(house_id)
    assert house is not None
    code = house.chat_binding_code
    chat_id = _chat_id()

    await _added_by(task_broker, chat_id, initiator_max_user_id=client.user.id)
    assert CODE_TEXT.format(title=CHAT_TITLE) in (
        message_manager.last_message().body.text or ""
    )
    assert _shown(shows, CODE_TEXT.format(title=CHAT_TITLE))[0] is ShowMode.SEND
    await client.send("не тот код")
    assert WRONG_CODE in (message_manager.last_message().body.text or "")
    await client.send(code)
    chat_api.is_admin = True
    await client.click(message_manager.last_message(), RIGHTS_DONE)

    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert BOUND_TEXT.format(title=CHAT_TITLE) in notices.texts
    bot_session.expire_all()
    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None
    assert chat.house_id == house_id


async def test_a_house_chat_event_creates_no_user(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    stranger = BotClient(bot_setup.dp, user_id=_max_id(), bot=fake_bot).user
    chat_id = _chat_id()

    await bot_setup.dp.feed_update(
        MaxoUpdate(
            update=BotAddedToChat(
                chat_id=chat_id,
                is_channel=False,
                user=stranger,
                timestamp=datetime.now(UTC),
            ).as_(fake_bot),
        ),
        fake_bot,
    )

    assert await _saved(bot_session, MaxUserId(stranger.id)) is None
    assert bot_broker.enqueued(TaskName.ON_BOT_ADDED)[-1] == {
        "chat_id": chat_id,
        "is_channel": False,
        "initiator_max_user_id": stranger.id,
    }


async def test_a_bot_that_is_no_longer_in_the_chat_is_not_its_admin(
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def forbidden(**_: Any) -> Any:
        raise MaxBotForbiddenError(code="chat.denied", error="", message="")

    monkeypatch.setattr(fake_bot, "get_membership", forbidden)

    assert await is_chat_admin(fake_bot, _chat_id()) is False


async def _bound_chat(session: AsyncSession, client: BotClient) -> MaxChatId:
    house_id = await _staff(session, client)
    user = await _saved(session, MaxUserId(client.user.id))
    assert user is not None
    chat_id = _chat_id()
    session.add(
        Chat(
            chat_id=chat_id,
            house_id=house_id,
            title=CHAT_TITLE,
            bound_by=user.id,
            bound_at=datetime.now(UTC),
            bot_is_admin=True,
            status=ChatStatus.ACTIVE,
        ),
    )
    await session.commit()
    return chat_id


@pytest.fixture
def refusing_chats(fake_bot: FakeBot, monkeypatch: pytest.MonkeyPatch) -> None:
    async def forbidden(**_: Any) -> Any:
        raise MaxBotForbiddenError(code="chat.denied", error="", message="")

    monkeypatch.setattr(fake_bot, "send_message", forbidden)


async def _broadcast(broker: InMemoryBroker, chat_id: MaxChatId) -> int:
    task: Any = broadcast_to_chats
    sent = (
        await task.kicker()
        .with_broker(broker)
        .kiq(chat_ids=[chat_id], text="Отключат воду")
    )
    result = await sent.wait_result(timeout=5)
    assert not result.is_err, result.error
    return cast(int, result.return_value)


@pytest.mark.usefixtures("refusing_chats")
async def test_a_failed_chat_send_asks_the_binder_for_the_rights_again(
    client: BotClient,
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,  # noqa: ARG001
    bot_session: AsyncSession,
    shows: list[Show],
) -> None:
    chat_id = await _bound_chat(bot_session, client)

    assert await _broadcast(task_broker, chat_id) == 0

    bot_session.expire_all()
    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None
    assert chat.bot_is_admin is False
    mode, _, recipient, notify = _shown(shows, RIGHTS_TEXT.format(title=CHAT_TITLE))
    assert mode is ShowMode.SEND
    assert recipient == client.chat.chat_id
    assert notify is True


@pytest.mark.usefixtures("refusing_chats")
async def test_a_failed_send_to_a_chat_with_rights_calls_nobody(
    client: BotClient,
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
    shows: list[Show],
) -> None:
    chat_api.is_admin = True
    chat_id = await _bound_chat(bot_session, client)

    await _broadcast(task_broker, chat_id)

    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None
    assert chat.bot_is_admin is True
    rights = RIGHTS_TEXT.format(title=CHAT_TITLE)
    assert not [show for show in shows if rights in (show[1] or "")]


async def _bot_removed(client: BotClient, chat_id: MaxChatId) -> None:
    await _feed(
        client,
        BotRemovedFromChat(
            chat_id=chat_id,
            is_channel=False,
            user=client.user,
            timestamp=datetime.now(UTC),
        ),
    )


async def _code_window(
    session: AsyncSession,
    client: BotClient,
    broker: InMemoryBroker,
) -> tuple[MaxChatId, str]:
    user_id = await _started(session, client)
    _, house_id = await _org_house(session)
    session.add(Resident(user_id=user_id, house_id=house_id, role=ResidentRole.OWNER))
    await session.commit()
    house = await HousesRepo(session).get(house_id)
    assert house is not None
    code = house.chat_binding_code
    chat_id = _chat_id()
    await _added_by(broker, chat_id, initiator_max_user_id=client.user.id)
    return chat_id, code


@pytest.mark.usefixtures("chat_api")
async def test_a_code_for_a_chat_the_bot_left_ends_on_the_menu(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    chat_id, code = await _code_window(bot_session, client, task_broker)
    await _bot_removed(client, chat_id)
    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None
    assert chat.status == ChatStatus.REMOVED

    await client.send(code)

    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert CHAT_TAKEN in notices.texts


@pytest.mark.usefixtures("chat_api")
async def test_rights_for_a_chat_the_bot_left_end_on_the_menu(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    shows: list[Show],
    notices: _RecordingBot,
) -> None:
    chat_id, code = await _code_window(bot_session, client, task_broker)
    await client.send(code)
    await _bot_removed(client, chat_id)
    shows.clear()

    await client.click(message_manager.last_message(), RIGHTS_DONE)

    assert _shown(shows, MENU_TEXT)[0] is ShowMode.SEND
    assert CHAT_NOT_BOUND in notices.texts
    assert notices.chat_ids == [client.chat.chat_id]


async def _feed(client: BotClient, update: Any) -> None:
    await client.dp.feed_update(MaxoUpdate(update=update.as_(client.bot)), client.bot)


async def _events_of(session: AsyncSession, user_id: UserId, event: EventType) -> int:
    stmt = select(events_table).where(
        events_table.c.type == event,
        events_table.c.user_id == user_id,
    )
    return len((await session.execute(stmt)).all())


@pytest.mark.parametrize("muted", [True, False])
async def test_mute_and_unmute_are_recorded(
    client: BotClient,
    bot_session: AsyncSession,
    muted: bool,
) -> None:
    user_id = await _started(bot_session, client)
    now = datetime.now(UTC)

    await _feed(
        client,
        (
            DialogMuted(
                chat_id=client.chat.chat_id,
                muted_until=now,
                user=client.user,
                timestamp=now,
            )
            if muted
            else DialogUnmuted(
                chat_id=client.chat.chat_id,
                user=client.user,
                timestamp=now,
            )
        ),
    )

    event = EventType.BOT_MUTED if muted else EventType.BOT_UNMUTED
    assert await _events_of(bot_session, user_id, event) == 1


async def test_the_welcome_carries_the_link_to_the_house(
    task_broker: InMemoryBroker,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    async def recording(**kwargs: Any) -> Any:
        sent.append(kwargs)
        return None

    monkeypatch.setattr(fake_bot, "send_message", recording)
    chat_id = _chat_id()
    house_id = HouseId(secrets.randbits(20))

    await _run(task_broker, welcome_chat, chat_id=chat_id, house_id=house_id)

    [message] = sent
    assert message["chat_id"] == chat_id
    assert message["notify"] is False
    [attachment] = message["attachments"]
    assert attachment.payload.buttons == [
        [
            LinkButton(
                text=JOIN_HOUSE,
                url=create_start_link(fake_bot, house_payload(house_id)),
            ),
        ],
    ]


async def test_the_bot_leaves_a_chat_added_by_an_executor(
    client: BotClient,
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
) -> None:
    user_id = await _started(bot_session, client)
    org_id, _ = await _org_house(bot_session)
    bot_session.add(OrgMember(org_id=org_id, user_id=user_id, role=OrgRole.EXECUTOR))
    await bot_session.commit()
    chat_id = _chat_id()

    await _added_by(task_broker, chat_id, initiator_max_user_id=client.user.id)

    assert chat_api.left == [chat_id]


@pytest.mark.parametrize("chairman", [False, True])
async def test_the_bot_leaves_a_chat_added_by_a_blocked_resident(
    client: BotClient,
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
    chairman: bool,
) -> None:
    user_id = await _started(bot_session, client)
    _, house_id = await _org_house(bot_session)
    bot_session.add(
        Resident(
            user_id=user_id,
            house_id=house_id,
            role=ResidentRole.OWNER,
            status=ResidentStatus.BLOCKED,
            is_chairman=chairman,
        ),
    )
    await bot_session.commit()
    chat_id = _chat_id()

    await _added_by(task_broker, chat_id, initiator_max_user_id=client.user.id)

    assert chat_api.left == [chat_id]


@pytest.mark.usefixtures("chat_api")
async def test_a_delivered_chat_message_is_counted(
    client: BotClient,
    task_broker: InMemoryBroker,
    bot_session: AsyncSession,
) -> None:
    chat_id = await _bound_chat(bot_session, client)

    assert await _broadcast(task_broker, chat_id) == 1


FIRST_SLOT = InlineButtonTextLocator("🕐 10:00")
ACCESS_REASON = "Поверка газового оборудования"


async def _access_window(
    session: AsyncSession,
    client: BotClient,
    broker: InMemoryBroker,
) -> tuple[AccessRequestId, AccessSlotId, FlatId]:
    user_id = await _started(session, client)
    org_id, house_id = await _org_house(session)
    mine, other = (
        Flat(house_id=house_id, number="1"),
        Flat(house_id=house_id, number="2"),
    )
    session.add_all([mine, other])
    await session.flush()
    session.add(
        Resident(
            user_id=user_id,
            house_id=house_id,
            flat_id=mine.id,
            role=ResidentRole.OWNER,
            verified_at=datetime.now(UTC),
        ),
    )
    access = AccessRepo(session)
    request = await access.create_request(
        org_id,
        house_id,
        ACCESS_REASON,
        datetime.now(UTC).date() + timedelta(days=1),
        user_id,
    )
    day = datetime.combine(request.date, time(10), tzinfo=ZoneInfo("Europe/Moscow"))
    [slot, _] = await access.add_slots(
        request.id,
        [(day, 1), (day + timedelta(hours=1), 1)],
    )
    await access.add_targets(request.id, [mine.id, other.id])
    ids = request.id, slot.id, other.id
    await session.commit()
    await _run(broker, broadcast_access_request, access_request_id=ids[0])
    return ids


async def test_a_full_slot_rerenders_the_access_window(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    request_id, slot_id, other = await _access_window(bot_session, client, task_broker)
    window = message_manager.last_message()
    stmt = (
        update(access_targets_table)
        .where(
            access_targets_table.c.access_request_id == request_id,
            access_targets_table.c.flat_id == other,
        )
        .values(slot_id=slot_id)
    )
    await bot_session.execute(stmt)
    await bot_session.commit()

    await client.click(window, FIRST_SLOT)

    rerendered = message_manager.last_message()
    assert ACCESS_REASON in (rerendered.body.text or "")
    assert SLOT_FULL in (rerendered.body.text or "")
    assert FIRST_SLOT.find_button(rerendered) is None


async def test_a_picked_slot_is_marked_in_the_access_window(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    shows: list[Show],
) -> None:
    await _access_window(bot_session, client, task_broker)
    mode, _, chat_id, _ = _shown(shows, ACCESS_REASON)
    assert mode is ShowMode.SEND
    assert chat_id == client.chat.chat_id

    await client.click(message_manager.last_message(), FIRST_SLOT)

    picked = InlineButtonTextLocator(PICKED.format(time="10:00"))
    assert picked.find_button(message_manager.last_message()) is not None


async def test_an_access_window_of_a_lost_flat_renders_instead_of_failing(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _access_window(bot_session, client, task_broker)
    window = message_manager.last_message()
    stmt = (
        update(residents_table)
        .where(residents_table.c.user_id == await _started(bot_session, client))
        .values(verified_at=None)
    )
    await bot_session.execute(stmt)
    await bot_session.commit()

    await client.click(window, FIRST_SLOT)

    assert GONE_TEXT in (message_manager.last_message().body.text or "")


async def test_a_block_reason_with_markup_renders_in_the_access_window(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _access_window(bot_session, client, task_broker)
    window = message_manager.last_message()
    stmt = (
        update(residents_table)
        .where(residents_table.c.user_id == await _started(bot_session, client))
        .values(status=ResidentStatus.BLOCKED, block_reason="долг <3 мес>")
    )
    await bot_session.execute(stmt)
    await bot_session.commit()

    await client.click(window, FIRST_SLOT)

    assert "долг &lt;3 мес&gt;" in (message_manager.last_message().body.text or "")


async def _bot_demo(session: AsyncSession, number: int = 1) -> tuple[OrgId, str]:
    org = await OrgsRepo(session).get_by_inn(DEMO_INNS[number - 1])
    if org is not None:
        org_id = org.id
    else:
        org = Organization(
            timezone="Europe/Moscow",
            name=f"Демо-УК «{number}»",
            inn=DEMO_INNS[number - 1],
            phone="+70000000000",
            address="Демо",
            registered_at=datetime.now(UTC),
            is_demo=True,
        )
        session.add(org)
        await session.flush()
        org_id = org.id
        session.add(
            House(
                timezone="Europe/Moscow",
                org_id=org_id,
                region="Демо",
                city="Демоград",
                street="Демо",
                building=str(number),
                chat_binding_code=secrets.token_hex(4),
            ),
        )
        await session.commit()
    houses = await HousesRepo(session).list_for_org(org_id)
    return OrgId(org_id), houses[0].address


async def _demo_roles(
    session: AsyncSession,
    client: BotClient,
) -> tuple[list[tuple[OrgId, OrgRole]], list[HouseId]]:
    user = await _saved(session, MaxUserId(client.user.id))
    assert user is not None
    members = select(org_members_table.c.org_id, org_members_table.c.role).where(
        org_members_table.c.user_id == user.id,
    )
    residents = select(residents_table.c.house_id).where(
        residents_table.c.user_id == user.id,
    )
    return (
        [(row.org_id, row.role) for row in await session.execute(members)],
        list((await session.execute(residents)).scalars()),
    )


@pytest.mark.parametrize(
    ("payload", "number"),
    [("demo_resident_1", 1), ("demo_resident_2", 2)],
)
async def test_a_demo_resident_link_gives_only_a_flat_in_its_organization(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    payload: str,
    number: int,
    notices: _RecordingBot,
) -> None:
    org_id, address = await _bot_demo(bot_session, number)
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)

    await _bot_started(client, payload)

    user = await _saved(bot_session, MaxUserId(client.user.id))
    assert user is not None
    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert (
        DEMO_RESIDENT_NOTICE.format(
            flat=demo_flat_number(user.id),
            address=address,
            org=f"Демо-УК «{number}»",
        )
        in notices.texts
    )
    houses = await HousesRepo(bot_session).list_for_org(org_id)
    assert await _demo_roles(bot_session, client) == ([], [houses[0].id])
    sources = [
        event.payload["source"] for event in await _starts_of(bot_session, client)
    ]
    assert sources.count(EventSource.DEEPLINK.value) == 1


async def test_a_demo_link_without_consent_asks_for_it_and_then_grants_access(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    org_id, _address = await _bot_demo(bot_session)

    await _bot_started(client, "demo_staff_1")
    assert CONSENT_TEXT in (message_manager.last_message().body.text or "")
    await client.click(message_manager.last_message(), ACCEPT)

    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert DEMO_STAFF_NOTICE.format(org="Демо-УК «1»") in notices.texts
    assert await _demo_roles(bot_session, client) == (
        [(org_id, OrgRole.EMPLOYEE)],
        [],
    )
    sources = [
        event.payload["source"] for event in await _starts_of(bot_session, client)
    ]
    assert sources == [EventSource.DEEPLINK.value]


async def test_a_demo_staff_link_lowers_a_demo_admin_to_an_employee(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    org_id, _address = await _bot_demo(bot_session, 3)
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)

    await _bot_started(client, "demo_admin_3")
    assert MENU_TEXT in (message_manager.last_message().body.text or "")
    assert DEMO_ADMIN_NOTICE.format(org="Демо-УК «3»") in notices.texts
    assert await _demo_roles(bot_session, client) == ([(org_id, OrgRole.ADMIN)], [])

    await _bot_started(client, "demo_staff_3")
    assert await _demo_roles(bot_session, client) == (
        [(org_id, OrgRole.EMPLOYEE)],
        [],
    )


async def test_a_house_without_a_connected_org_takes_no_request_in_the_bot(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    house_id, address = await _bot_house(bot_session)
    await _linked(bot_session, client, house_id, datetime.now(UTC))

    await client.click(message_manager.last_message(), NEW_REQUEST)

    text = message_manager.last_message().body.text or ""
    assert NOT_CONNECTED_TEXT.format(address=address) in text
    assert FIRST_CATEGORY.find_button(message_manager.last_message()) is None


class _PinApi:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.edited: list[dict[str, Any]] = []
        self.pinned: list[dict[str, Any]] = []
        self.deleted: list[str] = []
        self.edit_fails = False
        self.current: str | None = None

    async def send_message(self, **kwargs: Any) -> SendMessageResult:
        self.sent.append(kwargs)
        return SendMessageResult(
            message=Message(
                recipient=Recipient(chat_type=ChatType.CHAT, chat_id=kwargs["chat_id"]),
                timestamp=datetime.now(UTC),
                body=MessageBody(
                    mid=f"list-{len(self.sent)}",
                    seq=len(self.sent),
                    text=kwargs["text"],
                ),
            ),
        )

    async def edit_message(self, **kwargs: Any) -> SimpleQueryResult:
        if self.edit_fails:
            raise MaxBotNotFoundError(code="not.found", error="", message="")
        self.edited.append(kwargs)
        return SimpleQueryResult(success=True)

    async def pin_message(self, **kwargs: Any) -> SimpleQueryResult:
        self.pinned.append(kwargs)
        return SimpleQueryResult(success=True)

    async def delete_message(self, *, message_id: str, **_: Any) -> SimpleQueryResult:
        self.deleted.append(message_id)
        return SimpleQueryResult(success=True)

    async def get_pinned_message(self, *, chat_id: int) -> GetPinnedMessageResult:
        if self.current is None:
            return GetPinnedMessageResult(message=None)
        return GetPinnedMessageResult(
            message=Message(
                recipient=Recipient(chat_type=ChatType.CHAT, chat_id=chat_id),
                timestamp=datetime.now(UTC),
                body=MessageBody(mid=self.current, seq=1, text=""),
            ),
        )


@pytest.fixture
def pin_api(fake_bot: FakeBot, monkeypatch: pytest.MonkeyPatch) -> _PinApi:
    api = _PinApi()
    for name in (
        "send_message",
        "edit_message",
        "pin_message",
        "delete_message",
        "get_pinned_message",
    ):
        monkeypatch.setattr(fake_bot, name, getattr(api, name))
    return api


async def _listed_chat(
    session: AsyncSession,
    client: BotClient,
    *texts: str | None,
    pins_mid: str | None = None,
) -> tuple[MaxChatId, HouseId]:
    chat_id = await _bound_chat(session, client)
    user = await _saved(session, MaxUserId(client.user.id))
    assert user is not None
    chat = await ChatsRepo(session).get(chat_id)
    assert chat is not None
    assert chat.house_id is not None
    house_id = chat.house_id
    chat.pins_mid = pins_mid
    session.add_all(
        ChatPin(chat_id=chat_id, mid=f"m-{seq}", seq=seq, text=text, pinned_by=user.id)
        for seq, text in enumerate(texts, start=1)
    )
    await session.commit()
    return chat_id, house_id


async def _pins_mid(session: AsyncSession, chat_id: MaxChatId) -> str | None:
    session.expire_all()
    chat = await ChatsRepo(session).get(chat_id)
    assert chat is not None
    return chat.pins_mid


async def test_the_pin_list_is_sent_with_the_house_button_and_pinned_silently(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    fake_bot: FakeBot,
    bot_session: AsyncSession,
) -> None:
    chat_id, house_id = await _listed_chat(bot_session, client, "Вода <10:00>", None)

    await _run(task_broker, sync_chat_pins, chat_id=chat_id, notify=False)

    [sent] = pin_api.sent
    first, second = id_to_message_url(1, chat_id), id_to_message_url(2, chat_id)
    assert sent["text"] == (
        f'{PINS_TITLE}\n1. <a href="{first}">Вода &lt;10:00&gt;</a>\n2. {second}'
    )
    assert sent["notify"] is False
    [attachment] = sent["attachments"]
    assert attachment.payload.buttons == [
        [
            LinkButton(
                text=JOIN_HOUSE,
                url=create_start_link(fake_bot, house_payload(house_id)),
            ),
        ],
    ]
    assert pin_api.pinned == [
        {"chat_id": chat_id, "message_id": "list-1", "notify": False},
    ]
    assert await _pins_mid(bot_session, chat_id) == "list-1"


async def test_the_pin_list_edits_its_message_keeps_the_button_and_the_pin(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
) -> None:
    chat_id, _ = await _listed_chat(bot_session, client, "Вода", pins_mid="list-7")
    pin_api.current = "list-7"

    await _run(task_broker, sync_chat_pins, chat_id=chat_id, notify=False)

    assert pin_api.sent == []
    [edited] = pin_api.edited
    assert edited["message_id"] == "list-7"
    url = id_to_message_url(1, chat_id)
    assert edited["text"] == f'{PINS_TITLE}\n1. <a href="{url}">Вода</a>'
    assert edited["notify"] is False
    [attachment] = edited["attachments"]
    assert [[button.text for button in row] for row in attachment.payload.buttons] == [
        [JOIN_HOUSE],
    ]
    assert pin_api.pinned == []


async def test_a_list_message_that_cannot_be_edited_is_sent_anew(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
) -> None:
    pin_api.edit_fails = True
    chat_id, _ = await _listed_chat(bot_session, client, "Вода", pins_mid="list-7")

    await _run(task_broker, sync_chat_pins, chat_id=chat_id, notify=False)

    assert len(pin_api.sent) == 1
    assert pin_api.pinned[-1]["message_id"] == "list-1"
    assert await _pins_mid(bot_session, chat_id) == "list-1"


async def test_an_emptied_list_is_deleted_and_forgotten(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
) -> None:
    chat_id, _ = await _listed_chat(bot_session, client, pins_mid="list-7")

    await _run(task_broker, sync_chat_pins, chat_id=chat_id, notify=False)

    assert pin_api.deleted == ["list-7"]
    assert pin_api.sent == []
    assert pin_api.pinned == []
    assert await _pins_mid(bot_session, chat_id) is None


@pytest.mark.parametrize(
    ("failing", "texts", "pins_mid"),
    [
        ("send_message", ("Вода",), None),
        ("pin_message", ("Вода",), None),
        ("delete_message", (), "list-7"),
    ],
)
async def test_a_list_the_bot_cannot_post_asks_the_binder_for_the_rights(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,  # noqa: ARG001
    chat_api: _ChatApi,  # noqa: ARG001
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
    bot_session: AsyncSession,
    shows: list[Show],
    failing: str,
    texts: tuple[str, ...],
    pins_mid: str | None,
) -> None:
    async def forbidden(**_: Any) -> Any:
        raise MaxBotForbiddenError(code="chat.denied", error="", message="")

    monkeypatch.setattr(fake_bot, failing, forbidden)
    chat_id, _ = await _listed_chat(bot_session, client, *texts, pins_mid=pins_mid)

    await _run(task_broker, sync_chat_pins, chat_id=chat_id, notify=False)

    _, _, recipient, notify = _shown(shows, RIGHTS_TEXT.format(title=CHAT_TITLE))
    assert recipient == client.chat.chat_id
    assert notify is True


def _chat_message(chat_id: MaxChatId, mid: str, seq: int) -> Message:
    return Message(
        recipient=Recipient(chat_type=ChatType.CHAT, chat_id=chat_id),
        timestamp=datetime.now(UTC),
        body=MessageBody(mid=mid, seq=seq, text="Во вторник отключат воду"),
    )


def _in_chat(
    bot_setup: BotSetup,
    bot: FakeBot,
    chat_id: MaxChatId,
    max_user_id: int,
) -> BotClient:
    return BotClient(
        bot_setup.dp,
        user_id=max_user_id,
        chat_id=chat_id,
        chat_type=ChatType.CHAT,
        bot=bot,
    )


async def _pinned(
    session: AsyncSession,
    client: BotClient,
    chat_id: MaxChatId,
    *mids: str,
) -> None:
    user = await _saved(session, MaxUserId(client.user.id))
    assert user is not None
    session.add_all(
        ChatPin(chat_id=chat_id, mid=mid, seq=seq, pinned_by=user.id)
        for seq, mid in enumerate(mids, start=1)
    )
    await session.commit()


async def _pin_mids(session: AsyncSession, chat_id: MaxChatId) -> list[str]:
    session.expire_all()
    return [pin.mid for pin in await ChatsRepo(session).list_pins(chat_id)]


async def test_a_pin_in_the_house_chat_lists_the_replied_message(
    client: BotClient,
    bot_setup: BotSetup,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    chat_id = await _bound_chat(bot_session, client)
    recorder = _RecordingBot()
    group = _in_chat(bot_setup, recorder, chat_id, client.user.id)

    await group.send("/pin Отключение воды", reply_to=_chat_message(chat_id, "m-7", 7))

    bot_session.expire_all()
    [pin] = await ChatsRepo(bot_session).list_pins(chat_id)
    assert (pin.mid, pin.seq, pin.text) == ("m-7", 7, "Отключение воды")
    assert bot_broker.enqueued(TaskName.SYNC_CHAT_PINS)[-1] == {
        "chat_id": chat_id,
        "notify": True,
    }
    assert recorder.texts == [PINNED]
    assert [link.type for link in recorder.links] == [MessageLinkType.REPLY]


async def test_unpin_takes_a_number_and_replies_in_the_chat(
    client: BotClient,
    bot_setup: BotSetup,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    chat_id = await _bound_chat(bot_session, client)
    await _pinned(bot_session, client, chat_id, "m-1", "m-2")
    recorder = _RecordingBot()
    group = _in_chat(bot_setup, recorder, chat_id, client.user.id)

    await group.send("/unpin 2")
    await group.send("/unpin")

    assert await _pin_mids(bot_session, chat_id) == ["m-1"]
    assert recorder.texts == [UNPINNED, UNPIN_HINT]
    assert bot_broker.enqueued(TaskName.SYNC_CHAT_PINS)[-1] == {
        "chat_id": chat_id,
        "notify": False,
    }
    assert [link.type for link in recorder.links] == [MessageLinkType.REPLY] * 2


async def test_a_pin_in_a_chat_without_a_house_gets_no_answer(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
) -> None:
    recorder = _RecordingBot()
    chat_id = _chat_id()
    group = _in_chat(bot_setup, recorder, chat_id, _max_id())

    await group.send("/pin", reply_to=_chat_message(chat_id, "m-1", 1))
    await group.send("/unpin")

    assert recorder.texts == []


@pytest.mark.parametrize("command", ["/pin", "/unpin"])
async def test_pin_in_a_private_dialog_is_a_loose_message(
    client: BotClient,
    message_manager: MockMessageManager,
    command: str,
) -> None:
    await client.send(command)

    assert CONSENT_TEXT in (message_manager.last_message().body.text or "")


async def test_deleting_the_list_message_in_the_chat_unpins_everything(
    client: BotClient,
    bot_session: AsyncSession,
) -> None:
    chat_id = await _bound_chat(bot_session, client)
    await _pinned(bot_session, client, chat_id, "m-1", "m-2")
    await bot_session.execute(
        update(chats_table)
        .where(chats_table.c.chat_id == chat_id)
        .values(pins_mid="list-1"),
    )
    await bot_session.commit()

    await _feed(
        client,
        MessageRemoved(
            message_id="list-1",
            chat_id=chat_id,
            user_id=client.user.id,
            timestamp=datetime.now(UTC),
        ),
    )

    assert await _pin_mids(bot_session, chat_id) == []


async def test_the_consent_tap_marks_the_message_and_sends_the_menu_anew(
    client: BotClient,
    message_manager: MockMessageManager,
    shows: list[Show],
) -> None:
    await client.send("/start")

    await client.click(message_manager.last_message(), ACCEPT)

    mode, text, *_ = _shown(shows, GIVEN_TEXT)
    assert mode is ShowMode.EDIT
    assert CONSENT_TEXT in (text or "")
    marked = next(
        message
        for message in message_manager.sent_messages
        if GIVEN_TEXT in (message.body.text or "")
    )
    assert marked.body.keyboard is None
    assert _shown(shows, MENU_TEXT)[0] is ShowMode.SEND


async def test_the_policy_button_opens_the_privacy_page_of_the_mini_app(
    client: BotClient,
    message_manager: MockMessageManager,
    fake_bot: FakeBot,
) -> None:
    await client.send("/start")

    keyboard = message_manager.last_message().body.keyboard
    assert keyboard is not None
    [policy] = [
        button
        for row in keyboard.buttons
        for button in row
        if isinstance(button, OpenAppButton)
    ]
    assert policy.web_app == fake_bot.state.info.username
    assert isinstance(policy.payload, str)
    assert json.loads(decode_payload(policy.payload)) == {"path": "/privacy"}


@pytest.mark.parametrize(
    ("link", "source"),
    [
        (None, EventSource.DIRECT),
        (DeeplinkKind.HOUSE, EventSource.CHAT),
        (DeeplinkKind.ENTRANCE_QR, EventSource.QR),
        (DeeplinkKind.DEMO_STAFF, EventSource.DEEPLINK),
    ],
)
async def test_a_consent_in_the_bot_records_where_the_resident_came_from(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    link: DeeplinkKind | None,
    source: EventSource,
) -> None:
    house_id, _address = await _bot_house(bot_session)
    await _bot_demo(bot_session)
    payloads: dict[DeeplinkKind | None, Omittable[str | None]] = {
        None: Omitted(),
        DeeplinkKind.HOUSE: house_payload(house_id),
        DeeplinkKind.ENTRANCE_QR: entrance_qr_payload(house_id, 1),
        DeeplinkKind.DEMO_STAFF: "demo_staff_1",
    }
    await _bot_started(client, payloads[link])

    await client.click(message_manager.last_message(), ACCEPT)

    user = await _saved(bot_session, MaxUserId(client.user.id))
    assert user is not None
    stmt = select(events_table.c.payload).where(
        events_table.c.type == EventType.CONSENT_GIVEN,
        events_table.c.user_id == user.id,
    )
    assert (await bot_session.execute(stmt)).scalars().all() == [
        {"source": source.value, "version": CONSENT_VERSION},
    ]


async def test_a_consent_given_in_the_mini_app_is_not_asked_again(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await client.send("/start")
    user = await _saved(bot_session, MaxUserId(client.user.id))
    assert user is not None
    await UsersRepo(bot_session).set_consent(user.id, CONSENT_VERSION)
    await bot_session.commit()

    await client.send("/start")

    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert CONSENT_TEXT not in text


@pytest.fixture
def notices(fake_bot: FakeBot, monkeypatch: pytest.MonkeyPatch) -> _RecordingBot:
    recorder = _RecordingBot()
    monkeypatch.setattr(fake_bot, "send_message", recorder.send_message)
    return recorder


@pytest.mark.parametrize("deeplinked", [True, False])
async def test_a_bot_start_over_an_open_menu_comes_as_a_new_message(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    shows: list[Show],
    deeplinked: bool,
) -> None:
    house_id, address = await _bot_house(bot_session)
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    shows.clear()

    await _bot_started(client, house_payload(house_id) if deeplinked else Omitted())

    assert _shown(shows, address if deeplinked else MENU_TEXT)[0] is ShowMode.SEND


async def test_a_deeplink_result_is_its_own_message_before_the_menu(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    shows: list[Show],
    notices: _RecordingBot,
) -> None:
    await _bot_demo(bot_session)
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    shows.clear()

    await _bot_started(client, "demo_staff_1")

    notice = DEMO_STAFF_NOTICE.format(org="Демо-УК «1»")
    assert notices.texts == [notice]
    assert notices.notifies == [False]
    assert notices.chat_ids == [client.chat.chat_id]
    mode, text, *_ = _shown(shows, MENU_TEXT)
    assert mode is ShowMode.SEND
    assert notice not in (text or "")


async def test_a_consent_survives_a_deeplink_target_that_refuses(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    await _bot_started(client, "demo_staff_5")

    await client.click(message_manager.last_message(), ACCEPT)

    user = await _saved(bot_session, MaxUserId(client.user.id))
    assert user is not None
    assert user.consent_at is not None
    stmt = select(events_table.c.type).where(
        events_table.c.type == EventType.CONSENT_GIVEN,
        events_table.c.user_id == user.id,
    )
    assert (await bot_session.execute(stmt)).scalars().all() == [
        EventType.CONSENT_GIVEN,
    ]
    assert notices.texts == [NOT_SEEDED]
    assert MENU_TEXT in (message_manager.last_message().body.text or "")


async def test_the_org_name_is_escaped_in_the_invite_notice(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    user_id = await _started(bot_session, client)
    org_name = f"УК <{secrets.token_hex(4)}> & {secrets.token_hex(4)}"
    org = Organization(
        timezone="Europe/Moscow",
        name=org_name,
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Тестовая область, Тестоград, Тестовая, 1",
        registered_at=datetime.now(UTC),
    )
    bot_session.add(org)
    await bot_session.flush()
    code = secrets.token_hex(4)
    bot_session.add(
        OrgInvite(
            code=code,
            org_id=org.id,
            role=OrgRole.EMPLOYEE,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            max_activations=1,
            created_by=user_id,
        ),
    )
    await bot_session.commit()
    await client.click(message_manager.last_message(), ACCEPT)

    await _bot_started(client, org_invite_payload(code))

    notice = ORG_JOINED.format(name=escape(org_name))
    assert notices.texts == [notice]


FIND_HOUSE = InlineButtonTextLocator("🔎 Найти дом")
BY_ADDRESS = InlineButtonTextLocator("🗺 Выбрать адрес")
BACK_BUTTON = InlineButtonTextLocator("⬅️ Назад")
NAVIGATION = ["⬅️ Назад", "🏠 Меню"]


async def _search_by_address(
    client: BotClient,
    message_manager: MockMessageManager,
) -> None:
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    await client.click(message_manager.last_message(), FIND_HOUSE)
    await client.click(message_manager.last_message(), BY_ADDRESS)


def _button_texts(message: Message) -> list[str]:
    keyboard = message.body.keyboard
    if keyboard is None:
        return []
    return [str(button.text) for row in keyboard.buttons for button in row]


def _spot() -> tuple[Decimal, Decimal]:
    return (
        Decimal(secrets.randbelow(60_000_000) + 10_000_000) / 1_000_000,
        Decimal(secrets.randbelow(170_000_000)) / 1_000_000,
    )


async def _send_location(client: BotClient, lat: Decimal, lon: Decimal) -> None:
    message = Message(
        sender=client.user,
        recipient=Recipient(chat_type=ChatType.DIALOG, chat_id=client.chat.chat_id),
        timestamp=datetime.now(UTC),
        body=MessageBody(
            mid=secrets.token_hex(4),
            seq=1,
            text=None,
            attachments=[LocationAttachment(latitude=float(lat), longitude=float(lon))],
        ),
    )
    await _feed(client, MessageCreated(message=message, timestamp=datetime.now(UTC)))


def _text(message_manager: MockMessageManager) -> str:
    return message_manager.last_message().body.text or ""


async def test_typing_narrows_each_address_step_and_picks_a_single_match(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    tag = secrets.token_hex(3)
    city, other_city = f"Ввод{tag}а", f"Ввод{tag}б"
    street, other_street = f"Улица{tag}а", f"Улица{tag}б"
    for building in ("5а", "5б", "9"):
        await _bot_house(bot_session, city=city, street=street, building=building)
    await _bot_house(bot_session, city=city, street=other_street)
    await _bot_house(bot_session, city=other_city, street=street)
    await _bot_house(bot_session, city=f"Прочий{tag}", street=street)
    await _bot_house(bot_session, city=city, street=f"Прочая{tag}")
    await _search_by_address(client, message_manager)

    await client.send(f"Ввод{tag}")
    assert _button_texts(message_manager.last_message()) == [
        f"🏙 {city}",
        f"🏙 {other_city}",
        *NAVIGATION,
    ]
    await client.send(f"Нет{tag}")
    assert MISSED_TEXT.format(missed=f"Нет{tag}") in _text(message_manager)
    await client.send(city)
    assert STREET_TEXT.format(city=city) in _text(message_manager)

    await client.send(f"Улица{tag}")
    assert _button_texts(message_manager.last_message()) == [
        f"🛣 {street}",
        f"🛣 {other_street}",
        *NAVIGATION,
    ]
    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert CITY_TEXT in _text(message_manager)
    assert _button_texts(message_manager.last_message()) != NAVIGATION
    await client.send(city)
    await client.send(f"Нет{tag}")
    assert MISSED_TEXT.format(missed=f"Нет{tag}") in _text(message_manager)
    await client.send(street)
    assert SEARCH_HOUSE_TEXT.format(street=street) in _text(message_manager)

    await client.send("5")
    assert _button_texts(message_manager.last_message()) == [
        "🏢 5а",
        "🏢 5б",
        *NAVIGATION,
    ]
    await client.send("7")
    assert MISSED_TEXT.format(missed="7") in _text(message_manager)
    await client.send("9")
    assert f"{city}, {street}, 9" in _text(message_manager)


async def test_the_location_button_on_the_method_window_lists_houses_nearby(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    lat, lon = _spot()
    await _bot_house(
        bot_session,
        street="Геопозиционная",
        building="3",
        lat=lat,
        lon=lon,
    )
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    await client.click(message_manager.last_message(), FIND_HOUSE)

    keyboard = message_manager.last_message().body.keyboard
    assert keyboard is not None
    [geo] = [
        button
        for row in keyboard.buttons
        for button in row
        if isinstance(button, RequestGeoLocationButton)
    ]
    assert geo.text == "📍 По геолокации"
    await _send_location(client, lat, lon)

    assert NEARBY_TEXT in _text(message_manager)
    assert _button_texts(message_manager.last_message()) == [
        "🏢 Геопозиционная, 3",
        *NAVIGATION,
    ]


@pytest.mark.parametrize("by_geo", [False, True])
async def test_back_from_the_house_list_returns_to_where_it_came_from(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    by_geo: bool,
) -> None:
    tag = secrets.token_hex(3)
    lat, lon = _spot()
    await _bot_house(
        bot_session,
        city=f"Назад{tag}",
        street=f"Улица{tag}",
        building="1",
        lat=lat,
        lon=lon,
    )
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    await client.click(message_manager.last_message(), FIND_HOUSE)
    if by_geo:
        await _send_location(client, lat, lon)
    else:
        await client.click(message_manager.last_message(), BY_ADDRESS)
        await client.send(f"Назад{tag}")
        await client.send(f"Улица{tag}")
    await client.send("нет такого")

    await client.click(message_manager.last_message(), BACK_BUTTON)

    text = _text(message_manager)
    assert (METHOD_TEXT if by_geo else STREET_TEXT.format(city=f"Назад{tag}")) in text
    assert "Не нашлось" not in text


async def test_the_menu_button_leaves_the_house_search(
    client: BotClient,
    message_manager: MockMessageManager,
) -> None:
    await _search_by_address(client, message_manager)

    await client.click(message_manager.last_message(), TO_MENU)

    assert MENU_TEXT in _text(message_manager)


async def test_the_search_escapes_the_address_it_prints(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    tag = secrets.token_hex(3)
    city, street = f"Разметка{tag} <&>", f"Улица{tag} <&>"
    _house_id, address = await _bot_house(
        bot_session,
        city=city,
        street=street,
        building="1",
    )
    await _search_by_address(client, message_manager)

    await client.send(f"<{tag}>")
    assert MISSED_TEXT.format(missed=escape(f"<{tag}>")) in _text(message_manager)
    await client.send(f"Разметка{tag}")
    assert STREET_TEXT.format(city=escape(city)) in _text(message_manager)
    await client.send(f"Улица{tag}")
    assert SEARCH_HOUSE_TEXT.format(street=escape(street)) in _text(message_manager)
    await client.send("1")
    assert escape(address) in _text(message_manager)


async def test_a_flat_picked_from_the_list_is_linked(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    tag = secrets.token_hex(3)
    house_id, address = await _bot_house(
        bot_session,
        city=f"Квартиры{tag}",
        street=f"Улица{tag}",
        building="1",
    )
    bot_session.add_all(
        [Flat(house_id=house_id, number=number) for number in ("10", "2", "1")],
    )
    await bot_session.commit()
    await _search_by_address(client, message_manager)
    await client.send(f"Квартиры{tag}")
    await client.send(f"Улица{tag}")
    await client.send("1")

    assert _text(message_manager) == FLAT_LIST_TEXT.format(address=address)
    assert _button_texts(message_manager.last_message()) == [
        "🚪 1",
        "🚪 2",
        "🚪 10",
        "⏭ Пропустить",
        *NAVIGATION,
    ]
    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert SEARCH_HOUSE_TEXT.format(street=f"Улица{tag}") in _text(message_manager)
    await client.send("1")
    await client.click(message_manager.last_message(), InlineButtonTextLocator("🚪 10"))

    user = await _saved(bot_session, MaxUserId(client.user.id))
    assert user is not None
    flat = await HousesRepo(bot_session).get_flat_by_number(house_id, "10")
    assert flat is not None
    stmt = select(residents_table.c.flat_id).where(
        residents_table.c.user_id == user.id,
        residents_table.c.house_id == house_id,
    )
    assert (await bot_session.execute(stmt)).scalars().all() == [flat.id]
    assert HOUSE_LINKED.format(address=address) in notices.texts


async def test_a_deeplinked_flat_step_asks_the_number_and_goes_back_to_the_method(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    house_id, address = await _bot_house(bot_session)
    await _bot_started(client, house_payload(house_id))
    await client.click(message_manager.last_message(), ACCEPT)

    assert _text(message_manager) == FLAT_NUMBER_TEXT.format(address=address)
    await client.click(message_manager.last_message(), BACK_BUTTON)

    assert METHOD_TEXT in _text(message_manager)


async def test_back_and_menu_walk_the_request_draft(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    _, house_id = await _org_house(bot_session)
    await _linked(bot_session, client, house_id, datetime.now(UTC))
    await client.click(message_manager.last_message(), NEW_REQUEST)

    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert "🛠 Что случилось?" in _text(message_manager)

    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.send("Течет кран на кухне")
    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert DESCRIPTION_TEXT in _text(message_manager)

    await client.send("Течет кран на кухне")
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert PHOTO_TEXT.format(photos=0) in _text(message_manager)

    await client.click(message_manager.last_message(), TO_MENU)
    assert MENU_TEXT in _text(message_manager)
    await client.click(message_manager.last_message(), NEW_REQUEST)
    await client.click(message_manager.last_message(), TO_MENU)
    assert MENU_TEXT in _text(message_manager)


async def test_typing_near_a_location_filters_the_whole_list_every_time(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    lat, lon = _spot()
    for building in ("15", "51", "151"):
        await _bot_house(
            bot_session,
            street="Сужения",
            building=building,
            lat=lat,
            lon=lon,
        )
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    await client.click(message_manager.last_message(), FIND_HOUSE)
    await _send_location(client, lat, lon)

    await client.send("51")
    assert sorted(_button_texts(message_manager.last_message())) == sorted(
        ["🏢 Сужения, 51", "🏢 Сужения, 151", *NAVIGATION],
    )
    await client.send("15")
    assert sorted(_button_texts(message_manager.last_message())) == sorted(
        ["🏢 Сужения, 15", "🏢 Сужения, 151", *NAVIGATION],
    )


async def test_a_list_whose_content_changed_opens_on_its_first_page(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    tag = secrets.token_hex(3)
    city, first, second = f"Страницы{tag}", f"Первая{tag}", f"Вторая{tag}"
    for number in range(1, 21):
        await _bot_house(bot_session, city=city, street=first, building=str(number))
    for number in range(1, 11):
        await _bot_house(bot_session, city=city, street=second, building=str(number))
    await _search_by_address(client, message_manager)
    await client.send(city)
    await client.click(
        message_manager.last_message(),
        InlineButtonTextLocator(f"🛣 {first}"),
    )
    await client.click(message_manager.last_message(), InlineButtonTextLocator("3"))

    await client.send("1")
    assert _button_texts(message_manager.last_message())[0] == "🏢 1"

    await client.click(message_manager.last_message(), InlineButtonTextLocator("2"))
    await client.click(message_manager.last_message(), BACK_BUTTON)
    await client.click(
        message_manager.last_message(),
        InlineButtonTextLocator(f"🛣 {second}"),
    )
    assert _button_texts(message_manager.last_message())[0] == "🏢 1"


async def test_the_request_draft_escapes_the_address_and_the_description(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    _, house_id = await _org_house(bot_session)
    stmt = (
        update(houses_table)
        .where(houses_table.c.id == house_id)
        .values(street=f"Разметки <&> {secrets.token_hex(3)}")
    )
    await bot_session.execute(stmt)
    await bot_session.commit()
    house = await HousesRepo(bot_session).get(house_id)
    assert house is not None
    await bot_session.refresh(house)
    address = house.address
    await _linked(bot_session, client, house_id, datetime.now(UTC))
    description = "Давление <2 & <b>течет</b>"

    await client.click(message_manager.last_message(), NEW_REQUEST)
    assert CATEGORY_TEXT.format(address=escape(address)) in _text(message_manager)
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.send(description)
    await client.click(message_manager.last_message(), NEXT)

    assert f"\n\n{escape(description)}\n\n" in _text(message_manager)
    assert CONFIRM_TEXT.split("{", 1)[0] in _text(message_manager)


async def test_back_from_a_deeplinked_flat_step_forgets_the_deeplink(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    tag = secrets.token_hex(3)
    deeplinked, _ = await _bot_house(bot_session)
    picked, _ = await _bot_house(
        bot_session,
        city=f"Забытый{tag}",
        street=f"Улица{tag}",
        building="1",
    )
    await _bot_started(client, entrance_qr_payload(deeplinked, 3))
    await client.click(message_manager.last_message(), ACCEPT)
    await client.click(message_manager.last_message(), BACK_BUTTON)
    await client.click(message_manager.last_message(), BY_ADDRESS)
    await client.send(f"Забытый{tag}")
    await client.send(f"Улица{tag}")
    await client.send("1")
    await client.click(
        message_manager.last_message(),
        InlineButtonTextLocator("⏭ Пропустить"),
    )

    user = await _saved(bot_session, MaxUserId(client.user.id))
    assert user is not None
    stmt = select(events_table.c.payload).where(
        events_table.c.type == EventType.HOUSE_LINKED,
        events_table.c.user_id == user.id,
    )
    [payload] = (await bot_session.execute(stmt)).scalars().all()
    assert payload["house_id"] == picked
    assert payload["source"] == EventSource.DIRECT.value
    assert payload["entrance"] is None


async def test_a_refused_deeplink_of_a_consented_user_ends_on_the_menu(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    shows: list[Show],
    notices: _RecordingBot,
) -> None:
    user_id = await _started(bot_session, client)
    await client.click(message_manager.last_message(), ACCEPT)
    shows.clear()

    await _bot_started(client, org_invite_payload(secrets.token_hex(4)))

    assert notices.texts == [INVITE_NOT_FOUND]
    assert notices.notifies == [False]
    assert notices.chat_ids == [client.chat.chat_id]
    assert _shown(shows, MENU_TEXT)[0] is ShowMode.SEND
    assert MENU_TEXT in _text(message_manager)
    assert await _events_of(bot_session, user_id, EventType.BOT_START) == 2


CANCEL = InlineButtonTextLocator("❌ Отмена")


async def test_cancelling_the_photo_prompt_opens_the_menu(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    request_id = await _executor_on(bot_session, client, RequestStatus.IN_PROGRESS)
    await _run(task_broker, send_executor_card, request_id=request_id)
    await client.click(message_manager.last_message(), READY)
    await _rendered(message_manager, RESULT_PHOTO_TEXT)

    await client.click(message_manager.last_message(), CANCEL)

    assert MENU_TEXT in _text(message_manager)


async def test_cancelling_the_rejection_prompt_opens_the_menu(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    request_id = await _reviewing(bot_session, client, task_broker)
    await client.click(message_manager.last_message(), REJECT)
    await _rendered(message_manager, REJECTION_TEXT)

    await client.click(message_manager.last_message(), CANCEL)

    assert MENU_TEXT in _text(message_manager)
    assert (await _status(bot_session, request_id)).status is RequestStatus.ON_REVIEW


@pytest.mark.usefixtures("chat_api")
async def test_cancelling_the_binding_code_opens_the_menu(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    user_id = await _started(bot_session, client)
    _, house_id = await _org_house(bot_session)
    bot_session.add(
        Resident(user_id=user_id, house_id=house_id, role=ResidentRole.OWNER),
    )
    await bot_session.commit()
    await _added_by(task_broker, _chat_id(), initiator_max_user_id=client.user.id)
    assert CODE_TEXT.format(title=CHAT_TITLE) in _text(message_manager)

    await client.click(message_manager.last_message(), CANCEL)

    assert MENU_TEXT in _text(message_manager)


@pytest.mark.parametrize("current", [None, "m-other"])
async def test_an_unpinned_list_is_pointed_at_instead_of_pinned_over(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
    current: str | None,
) -> None:
    chat_id, _ = await _listed_chat(bot_session, client, "Вода", pins_mid="list-7")
    pin_api.current = current

    await _run(task_broker, sync_chat_pins, chat_id=chat_id, notify=False)

    assert pin_api.pinned == []
    [reply] = pin_api.sent
    assert reply["text"] == PINS_HERE
    assert reply["link"] == NewMessageLink(mid="list-7", type=MessageLinkType.REPLY)
    assert reply["notify"] is False


@pytest.mark.parametrize("pins_mid", [None, "list-7"])
async def test_a_new_pin_pins_the_list_again_with_sound(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
    pins_mid: str | None,
) -> None:
    chat_id, _ = await _listed_chat(bot_session, client, "Вода", pins_mid=pins_mid)
    pin_api.current = "m-other"

    await _run(task_broker, sync_chat_pins, chat_id=chat_id, notify=True)

    mid = await _pins_mid(bot_session, chat_id)
    assert pin_api.pinned == [{"chat_id": chat_id, "message_id": mid, "notify": True}]
    assert PINS_HERE not in [sent["text"] for sent in pin_api.sent]
