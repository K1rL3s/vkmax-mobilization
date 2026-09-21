import asyncio
import secrets
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, time, timedelta
from typing import Any, cast

import pytest
from dishka import AsyncContainer
from maxo import Router
from maxo.dialogs import BgManagerFactory, ShowMode, StartMode
from maxo.dialogs.api.entities import NewMessage
from maxo.dialogs.context.media_storage import MediaIdStorage
from maxo.dialogs.test_tools import BotClient, MockMessageManager
from maxo.dialogs.test_tools.bot_client import FakeBot
from maxo.dialogs.test_tools.keyboard import InlineButtonTextLocator
from maxo.enums import ChatStatus as MaxChatStatus, ChatType
from maxo.errors import MaxBotForbiddenError
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
    Message,
    MessageBody,
    MessageCreated,
    OpenAppButton,
    PhotoAttachment,
    PhotoAttachmentPayload,
    Recipient,
    SendMessageResult,
)
from maxo.types.chat import Chat as MaxChat
from maxo.types.link_button import LinkButton
from maxo.types.simple_query_result import SimpleQueryResult
from maxo.types.update_context import UpdateContext
from maxo.utils.deeplink import create_start_link
from sqlalchemy import Row, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import InMemoryBroker

from tests.conftest import PROBE_ROUTERS, RecordingBroker

from zheka.bot import BotSetup
from zheka.bot.handlers.access.handlers import PICKED
from zheka.bot.handlers.access.windows import GONE_TEXT
from zheka.bot.handlers.chats.handlers import BOUND_TEXT, NO_RIGHTS_YET
from zheka.bot.handlers.chats.windows import CODE_TEXT, HOUSE_TEXT, RIGHTS_TEXT
from zheka.bot.handlers.executor.handlers import PHOTO_TAKEN
from zheka.bot.handlers.executor.windows import HANDED_OVER_TEXT, RESULT_PHOTO_TEXT
from zheka.bot.handlers.menu.windows import MENU_TEXT
from zheka.bot.handlers.review.handlers import repeat_sent
from zheka.bot.handlers.review.windows import ASK_TEXT, RATED_TEXT, REJECTION_TEXT
from zheka.bot.message_manager import ZhekaMessageManager
from zheka.bot.middlewares.user import private_chat_id
from zheka.bot.states import Consent, Menu
from zheka.broker.task_names import TaskName
from zheka.broker.tasks.chats import JOIN_HOUSE, on_bot_added, welcome_chat
from zheka.broker.tasks.notifications import broadcast_to_chats
from zheka.broker.tasks.reminders import broadcast_access_request
from zheka.broker.tasks.requests import (
    attach_result_photo,
    send_executor_card,
    send_review_card,
)
from zheka.core.consent import CONSENT_TEXT
from zheka.core.deeplinks import house_payload, org_invite_payload
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
from zheka.core.errors import NotEnoughRights
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
from zheka.core.services.chats import CHAT_NOT_BOUND, CHAT_TAKEN, WRONG_CODE
from zheka.core.services.orgs import INVITE_NOT_FOUND
from zheka.core.services.requests import MAX_RATING, MIN_RATING, REJECT_NOT_ON_REVIEW
from zheka.core.texts import REQUEST_STATUS_LABELS
from zheka.infra.database.models import (
    Chat,
    Flat,
    House,
    OrgMember,
    Organization,
    Request,
    Resident,
)
from zheka.infra.database.repos.access import AccessRepo
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.access import access_targets_table
from zheka.infra.database.tables.events import events_table
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

    async def send_message(  # type: ignore[mutable-override]
        self,
        *_: Any,
        **kwargs: Any,
    ) -> SendMessageResult:
        self.notifies.append(kwargs["notify"])
        self.texts.append(kwargs.get("text"))
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


ACCEPT = InlineButtonTextLocator("Согласен")
NEW_REQUEST = InlineButtonTextLocator("Подать заявку")
FIRST_CATEGORY = InlineButtonTextLocator(
    CATEGORY_RULES[next(iter(RequestCategory))].label,
)
NEXT = InlineButtonTextLocator("Дальше")
SEND = InlineButtonTextLocator("Отправить")
TO_MENU = InlineButtonTextLocator("В меню")


def _max_id() -> MaxUserId:
    return MaxUserId(secrets.randbits(40))


@pytest.fixture
def client(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    message_manager: MockMessageManager,
) -> BotClient:
    # свой max_user_id на тест: хранилище стеков у прогона одно, и чужое
    # состояние не должно протекать в соседний тест
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


async def test_start_without_consent_renders_the_consent_window(
    client: BotClient,
    message_manager: MockMessageManager,
) -> None:
    await client.send("/start")

    assert CONSENT_TEXT in (message_manager.last_message().body.text or "")


async def test_consent_button_writes_the_consent_and_opens_the_menu(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await client.send("/start")

    await client.click(message_manager.last_message(), ACCEPT)

    user = await _saved(bot_session, MaxUserId(client.user.id))
    assert user is not None
    assert user.consent_at is not None
    assert user.consent_version is not None


async def test_start_writes_the_private_chat_id(
    client: BotClient,
    bot_session: AsyncSession,
) -> None:
    await client.send("/start")

    user = await _saved(bot_session, MaxUserId(client.user.id))
    assert user is not None
    assert user.max_chat_id == MaxChatId(client.chat.chat_id)


async def test_a_message_from_a_house_chat_starts_nothing(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    message_manager: MockMessageManager,
) -> None:
    # бот-администратор чата дома получает его сообщения, и онбординг в группе
    # начинаться не должен
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


async def test_upsert_keeps_the_chat_id_when_the_update_brings_none(
    session: AsyncSession,
) -> None:
    # прямая проверка coalesce: мини-апп апсертит без id личного диалога на
    # каждом запросе, и затертый max_chat_id навсегда отрезал бы жителя от окон
    repo = UsersRepo(session)
    max_user_id = _max_id()

    await repo.upsert_by_max_id(max_user_id, "Житель", None, MaxChatId(777))
    user = await repo.upsert_by_max_id(max_user_id, "Житель", None, None)

    assert user.max_chat_id == MaxChatId(777)


class _NotifyProbe:
    # фоновый менеджер-заглушка: запоминает звук, с которым start_dialog
    # вошел в fg(), и сам факт того, что до него дошли
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
    # ContextVar возвращается к продуктовому дефолту: молча
    assert dialog_notify.get() is False


async def test_a_user_without_a_private_chat_gets_no_window(
    fake_bot: FakeBot,
) -> None:
    probe = _NotifyProbe()
    sender = MaxSender(fake_bot, cast(BgManagerFactory, probe))
    user = User(id=UserId(1), max_user_id=_max_id(), name="Житель")

    await sender.start_dialog(Menu.main, user, notify=False)

    assert probe.notify is None


async def test_the_dialog_message_is_silent_unless_the_task_asked_for_sound() -> None:
    # MockMessageManager до bot.send_message не доходит, поэтому звук
    # проверяется на настоящем менеджере поверх пишущего бота
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

    # ни одного await между возвратом start_dialog и проверкой: bg().start()
    # отдал бы апдейт в call_soon и вернулся раньше отправки
    assert message_manager.sent_messages != []


async def test_a_window_opened_by_a_task_keeps_the_user_name(
    client: BotClient,
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    bot_session: AsyncSession,
) -> None:
    # DialogUpdateEvent несет FakeUser, собранный из одних id, с пустым именем
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
    # второй /start сбрасывает стек, и интент первой кнопки перестает
    # существовать: перезапуск на середине потока выглядит так же
    await client.send("/start")
    message_manager.reset_history()

    await client.click(stale, ACCEPT)

    assert MENU_TEXT in (message_manager.last_message().body.text or "")


@pytest.mark.parametrize(
    ("chat_type", "expected"),
    [(ChatType.DIALOG, MaxChatId(5)), (ChatType.CHAT, None), (ChatType.CHANNEL, None)],
)
def test_only_a_private_dialog_gives_the_chat_id_to_write(
    chat_type: ChatType,
    expected: MaxChatId | None,
) -> None:
    # у сообщения из чата дома chat_id чужой: записать его как личный - значит
    # открыть окно жителя всему дому. Апдейт из группы сейчас никем не
    # обрабатывается и откатывается целиком, поэтому проверка тут, а не в
    # прогоне через диспетчер
    context = UpdateContext(chat_id=5, user_id=1, type=chat_type)

    assert private_chat_id(context) == expected


async def test_the_start_is_recorded_once_and_a_loose_message_is_not_a_start(
    client: BotClient,
    bot_session: AsyncSession,
) -> None:
    # апдейт без состояния открывает то же окно, но стартом не является
    await client.send("здравствуйте")
    await client.send("/start")

    stmt = select(events_table).where(
        events_table.c.type == EventType.BOT_START,
        events_table.c.user_id.in_(
            select(users_table.c.id).where(
                users_table.c.max_user_id == client.user.id,
            ),
        ),
    )
    events = (await bot_session.execute(stmt)).all()

    assert len(events) == 1
    assert events[0].payload == {"source": "direct"}


async def test_the_menu_offers_the_mini_app_under_the_bot_username(
    client: BotClient,
    message_manager: MockMessageManager,
    fake_bot: FakeBot,
) -> None:
    await client.send("/start")

    await client.click(message_manager.last_message(), ACCEPT)

    keyboard = message_manager.last_message().body.keyboard
    assert keyboard is not None
    buttons = [button for row in keyboard.buttons for button in row]
    assert [
        button.web_app for button in buttons if isinstance(button, OpenAppButton)
    ] == [fake_bot.state.info.username]


async def test_a_tap_from_a_house_chat_renders_nothing(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    message_manager: MockMessageManager,
) -> None:
    # chat_type колбэка берется из recipient его сообщения, а ключ стека - из
    # того же chat_type, поэтому живое окно в ключах чата дома заводится
    # фоновым менеджером: иначе IntentMiddleware отвечает OutdatedIntent
    # раньше роутеров и до фильтра дело не доходит
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


async def test_a_user_who_stopped_the_bot_gets_no_window(
    fake_bot: FakeBot,
) -> None:
    # остановленному боту MAX отвечает 403: окно ему открывать незачем
    probe = _NotifyProbe()
    sender = MaxSender(fake_bot, cast(BgManagerFactory, probe))
    user = User(id=UserId(1), max_user_id=_max_id(), name="Житель")
    user.max_chat_id = MaxChatId(42)
    user.bot_stopped_at = datetime.now(UTC)

    await sender.start_dialog(Menu.main, user, notify=False)

    assert probe.notify is None


ERROR_PROBE_COMMAND = "errorprobe"
PROBE_DENIED = "Пробная доменная ошибка"

error_probe_router = Router(name="error-probe")
# в общий диспетчер из conftest: maxo запрещает include после старта
PROBE_ROUTERS.append(error_probe_router)


@error_probe_router.message_created(Command(ERROR_PROBE_COMMAND))
async def error_probe_handler(_update: MessageCreated) -> None:
    raise NotEnoughRights(PROBE_DENIED)


async def test_a_domain_error_on_a_message_is_answered(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
) -> None:
    # обработчик, вернувший None, для ErrorMiddleware разобран: без ответа
    # текстом ошибка ввода пропала бы вовсе
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
    # у личного диалога два разных id: ведро на max_chat_id было бы вторым на
    # тот же чат, и житель получал бы 4 сообщения в секунду вместо двух
    probe = _NotifyProbe()
    sender = MaxSender(fake_bot, cast(BgManagerFactory, probe))
    user = User(id=UserId(1), max_user_id=_max_id(), name="Житель")
    # оба id свои на тест: ведра кешируются на весь прогон, и общий chat_id
    # выдал бы зеленое из-за чужих вызовов, а не из-за общего ведра
    user.max_chat_id = MaxChatId(_max_id())
    bucket = _chat_rate_limit(user.max_user_id)

    async with bucket, bucket:
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.1):
                await sender.start_dialog(Menu.main, user, notify=False)

    assert probe.notify is None


async def _bot_started(client: BotClient, payload: Omittable[str | None]) -> None:
    await client.dp.feed_update(
        MaxoUpdate(
            update=BotStarted(
                chat_id=client.chat.chat_id,
                user=client.user,
                payload=payload,
                timestamp=datetime.now(UTC),
            ).as_(client.bot),
        ),
        client.bot,
    )


async def _bot_house(session: AsyncSession) -> tuple[HouseId, str]:
    house = House(
        region="Тестовая область",
        city="Тестоград",
        street="Диплинковая",
        building=secrets.token_hex(2),
        cadastral_no=secrets.token_hex(8),
        chat_binding_code=secrets.token_hex(4),
    )
    session.add(house)
    await session.commit()
    await session.refresh(house)
    return HouseId(house.id), house.address


async def _starts_of(session: AsyncSession, client: BotClient) -> Sequence[Row[Any]]:
    stmt = select(events_table).where(
        events_table.c.type == EventType.BOT_START,
        events_table.c.user_id.in_(
            select(users_table.c.id).where(
                users_table.c.max_user_id == client.user.id,
            ),
        ),
    )
    return (await session.execute(stmt)).all()


async def test_an_unparseable_payload_falls_through_to_start(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    # обработчик диплинков обязан вернуть UNHANDLED: вернув None, он съел бы
    # апдейт, и житель с опечаткой в ссылке получил бы немого бота
    await _bot_started(client, "не-диплинк")

    # сперва факт ответа, потом его текст: иначе съеденный апдейт падал бы
    # IndexError из last_message(), а не на проверке, которая его сторожит
    assert message_manager.sent_messages
    assert CONSENT_TEXT in (message_manager.last_message().body.text or "")
    events = await _starts_of(bot_session, client)
    assert len(events) == 1
    assert events[0].payload == {"source": EventSource.DIRECT.value}


async def test_a_plain_start_falls_through_to_start(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    # самый частый вход в бота: «Начать» без всякой ссылки. Тот же UNHANDLED,
    # что и у опечатки, но ветка своя - payload тут Omitted, а не строка
    await _bot_started(client, Omitted())

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
    # у BotStarted нет ни колбэка, ни сообщения, на которое отвечают, поэтому
    # протухшая ссылка приглашения иначе уходила бы в тишину
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
            user_id=UserId(user.id),
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
    # с двумя домами порядок выдачи базы ничего не решает: окно и задача
    # обязаны взять тот, который житель завел последним
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    now = datetime.now(UTC)
    first, _ = await _bot_house(bot_session)
    last, last_address = await _bot_house(bot_session)
    await _linked(bot_session, client, first, now)
    await _linked(bot_session, client, last, now + timedelta(minutes=1))

    address = await _draft_request(client, message_manager)

    assert last_address in address
    enqueued = bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)
    assert enqueued[-1]["house_id"] == int(last)


async def test_the_sent_window_leads_back_to_the_menu(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    # окно «Принял, оформляю» - терминальное состояние заявки, а живой диалог
    # глотает обычное сообщение: без кнопки из него нет дороги, кроме /start
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)
    house_id, _ = await _bot_house(bot_session)
    await _linked(bot_session, client, house_id, datetime.now(UTC))
    await _draft_request(client, message_manager)

    await client.click(message_manager.last_message(), TO_MENU)

    assert MENU_TEXT in (message_manager.last_message().body.text or "")


DEPART = InlineButtonTextLocator("Выехал")
READY = InlineButtonTextLocator("Готово")
REJECT = InlineButtonTextLocator("Сделано плохо")
RESULT_URL = "https://max.ru/result.jpg"
# dummy attachment token: the fake bot never downloads anything
PHOTO_TOKEN = "photo-token"  # noqa: S105


async def _org_house(session: AsyncSession) -> tuple[OrgId, HouseId]:
    org = Organization(
        name=f"УК {secrets.token_hex(4)}",
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Тестовая область, Тестоград, Тестовая, 1",
    )
    session.add(org)
    await session.flush()
    house = House(
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
    # после commit атрибуты протухают, и чтение id полезло бы в базу без await
    ids = OrgId(org.id), HouseId(house.id)
    await session.commit()
    return ids


async def _started(session: AsyncSession, client: BotClient) -> UserId:
    await client.send("/start")
    user = await _saved(session, MaxUserId(client.user.id))
    assert user is not None
    return UserId(user.id)


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
    request_id = RequestId(request.id)
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
    await client.dp.feed_update(
        MaxoUpdate(
            update=MessageCreated(
                message=message,
                timestamp=datetime.now(UTC),
            ).as_(client.bot),
        ),
        client.bot,
    )


async def _rendered(message_manager: MockMessageManager, text: str) -> None:
    # окно ввода открывает bg().start(): апдейт уходит в call_soon и
    # рисуется уже после ответа на нажатие. Задачу создает maxo и наружу не
    # отдает, так что ждать нечего, кроме самого сообщения
    async with asyncio.timeout(5):
        while not message_manager.sent_messages or text not in (  # noqa: ASYNC110
            message_manager.last_message().body.text or ""
        ):
            await asyncio.sleep(0.01)


async def test_a_tap_on_the_executor_card_moves_the_request(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    request_id = await _executor_on(bot_session, client, RequestStatus.ACCEPTED)
    request = await _status(bot_session, request_id)
    assert request.executor_user_id is not None
    message_manager.reset_history()

    await _run(task_broker, send_executor_card, request_id=request_id)
    await client.click(message_manager.last_message(), DEPART)

    assert (await _status(bot_session, request_id)).status is RequestStatus.IN_PROGRESS


async def test_ready_asks_for_the_photo_where_a_message_reaches_it(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    # сообщение maxo отдает только стеку по умолчанию: окно фото в стеке
    # карточки фото бы не дождалось, и оно ушло бы в fallback
    request_id = await _executor_on(bot_session, client, RequestStatus.IN_PROGRESS)
    request = await _status(bot_session, request_id)
    assert request.executor_user_id is not None
    await _run(task_broker, send_executor_card, request_id=request_id)
    await client.click(message_manager.last_message(), READY)
    await _rendered(message_manager, RESULT_PHOTO_TEXT)

    await _send_photo(client)

    assert bot_broker.enqueued(TaskName.ATTACH_RESULT_PHOTO)[-1] == {
        "user_id": request.executor_user_id,
        "request_id": request_id,
        "photo_urls": [RESULT_URL],
    }
    # окно фото не остается висеть в стеке по умолчанию и глотать сообщения
    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert PHOTO_TAKEN in text


async def test_a_rejection_on_the_review_card_opens_a_repeat_from_the_bot(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    author = await _started(bot_session, client)
    _, house_id = await _org_house(bot_session)
    bot_session.add(
        Resident(user_id=author, house_id=house_id, role=ResidentRole.OWNER),
    )
    await bot_session.commit()
    request_id = await _request(
        bot_session,
        house_id,
        RequestStatus.ON_REVIEW,
        author=author,
    )
    await _run(task_broker, send_review_card, request_id=request_id)

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
    assert repeat_sent(RequestId(repeat.id)) in text


ACCEPT_WORK = InlineButtonTextLocator("Принять")
TOP_RATING = InlineButtonTextLocator(str(MAX_RATING))

# режим, текст, чат и звук: звук start_dialog кладет в ContextVar вокруг fg(),
# и на входе в менеджер сообщений он еще виден
Show = tuple[ShowMode, str | None, int | None, bool]


@pytest.fixture
def shows(
    message_manager: MockMessageManager,
    monkeypatch: pytest.MonkeyPatch,
) -> list[Show]:
    # MockMessageManager шлет каждое окно новым сообщением, EDIT или нет;
    # а режим, о котором его попросили, виден только на входе
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


async def test_the_input_prompt_is_sent_as_a_new_message(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    shows: list[Show],
) -> None:
    # EDIT переписал бы последнее сообщение стека по умолчанию где-то выше в
    # истории, и житель не увидел бы, что бот ждет фото
    request_id = await _executor_on(bot_session, client, RequestStatus.IN_PROGRESS)
    await _run(task_broker, send_executor_card, request_id=request_id)

    await client.click(message_manager.last_message(), READY)
    await _rendered(message_manager, RESULT_PHOTO_TEXT)

    assert _shown(shows, RESULT_PHOTO_TEXT)[0] is ShowMode.SEND


async def test_cards_announcing_something_new_are_sent_not_edited(
    client: BotClient,
    task_broker: InMemoryBroker,
    bot_session: AsyncSession,
    shows: list[Show],
) -> None:
    # повторное назначение A -> B -> A правкой карточки выше в истории прошло
    # бы для A молча
    request_id = await _executor_on(bot_session, client, RequestStatus.ACCEPTED)
    await _run(task_broker, send_executor_card, request_id=request_id)
    await _run(task_broker, send_executor_card, request_id=request_id)

    cards = [mode for mode, text, *_ in shows if f"№{request_id}:" in (text or "")]
    assert cards == [ShowMode.SEND, ShowMode.SEND]


async def test_the_review_card_is_sent_to_the_author(
    client: BotClient,
    task_broker: InMemoryBroker,
    bot_session: AsyncSession,
    shows: list[Show],
) -> None:
    await _reviewing(bot_session, client, task_broker)

    mode, _, chat_id, _ = shows[-1]
    assert mode is ShowMode.SEND
    assert chat_id == client.chat.chat_id


async def test_a_stale_rejection_prompt_files_no_repeat(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    # житель передумал и принял работу на карточке, а окно отказа осталось:
    # следующее его сообщение не должно уйти в УК повторной заявкой
    request_id = await _reviewing(bot_session, client, task_broker)
    card = message_manager.last_message()
    await client.click(card, REJECT)
    await _rendered(message_manager, REJECTION_TEXT)
    await client.click(card, ACCEPT_WORK)

    await client.send("Спасибо, все хорошо")

    assert await _repeats_of(bot_session, request_id) == []
    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert REJECT_NOT_ON_REVIEW in text


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
    # заявку передали другому, пока фото ехало: отправитель видит, что она
    # уже не его, а не старую карточку с «Готово»
    request_id = await _executor_on(bot_session, client, RequestStatus.IN_PROGRESS)
    sender_id = await _started(bot_session, client)
    other = User(max_user_id=_max_id(), name="Другой исполнитель")
    bot_session.add(other)
    await bot_session.flush()
    other_id = UserId(other.id)
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
    await client.dp.feed_update(
        MaxoUpdate(
            update=BotStopped(
                chat_id=client.chat.chat_id,
                user=client.user,
                timestamp=datetime.now(UTC),
            ).as_(client.bot),
        ),
        client.bot,
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
    # то, что MAX знает о чате дома: название, выход бота и его права
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
    await _run(
        broker,
        on_bot_added,
        chat_id=chat_id,
        **{"is_channel": False, **kwargs},
    )


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
    # строку users без личного чата заводит мини-апп: окно открыть некуда
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


async def test_the_bot_leaves_a_chat_added_by_a_user_of_no_house(
    client: BotClient,
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
) -> None:
    await _started(bot_session, client)
    chat_id = _chat_id()

    await _added_by(task_broker, chat_id, initiator_max_user_id=client.user.id)

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
    await client.click(window, InlineButtonTextLocator(house.address))
    await client.click(message_manager.last_message(), READY)
    assert NO_RIGHTS_YET in (message_manager.last_message().body.text or "")
    chat_api.is_admin = True
    await client.click(message_manager.last_message(), READY)

    # окно дома живет в стеке чата: там «Готово» ведет на done, а в стеке по
    # умолчанию увело бы в меню
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
) -> None:
    user_id = await _started(bot_session, client)
    _, house_id = await _org_house(bot_session)
    bot_session.add(
        Resident(user_id=user_id, house_id=house_id, role=ResidentRole.OWNER)
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
    await client.click(message_manager.last_message(), READY)

    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert BOUND_TEXT.format(title=CHAT_TITLE) in text
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
    # из чата дома в users не пишется никто: согласия там никто не давал, а
    # бот-админ получает каждое сообщение
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
    # Any, как в _run: по сигнатуре kiq требует и то, что подставит dishka
    task: Any = broadcast_to_chats
    sent = (
        await task.kicker()
        .with_broker(broker)
        .kiq(
            chat_ids=[chat_id],
            text="Отключат воду",
            buttons=None,
        )
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
    # бот без прав глушит весь дом, пока привязавший не нажмет
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
    await client.dp.feed_update(
        MaxoUpdate(
            update=BotRemovedFromChat(
                chat_id=chat_id,
                is_channel=False,
                user=client.user,
                timestamp=datetime.now(UTC),
            ).as_(client.bot),
        ),
        client.bot,
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
) -> None:
    # окно кода живет в стеке по умолчанию: оставленное там, оно глотало бы
    # каждое сообщение жителя
    chat_id, code = await _code_window(bot_session, client, task_broker)
    await _bot_removed(client, chat_id)
    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None
    assert chat.status == ChatStatus.REMOVED

    await client.send(code)

    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert CHAT_TAKEN in text


@pytest.mark.usefixtures("chat_api")
async def test_rights_for_a_chat_the_bot_left_end_on_the_menu(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    chat_id, code = await _code_window(bot_session, client, task_broker)
    await client.send(code)
    await _bot_removed(client, chat_id)

    await client.click(message_manager.last_message(), READY)

    text = message_manager.last_message().body.text or ""
    assert MENU_TEXT in text
    assert CHAT_NOT_BOUND in text


async def _feed(client: BotClient, update: Any) -> None:
    await client.dp.feed_update(MaxoUpdate(update=update.as_(client.bot)), client.bot)


async def _events_of(
    session: AsyncSession,
    user_id: UserId,
    event: EventType,
) -> int:
    stmt = select(events_table).where(
        events_table.c.type == event,
        events_table.c.user_id == user_id,
    )
    return len((await session.execute(stmt)).all())


async def test_mute_is_recorded(client: BotClient, bot_session: AsyncSession) -> None:
    user_id = await _started(bot_session, client)

    await _feed(
        client,
        DialogMuted(
            chat_id=client.chat.chat_id,
            muted_until=datetime.now(UTC),
            user=client.user,
            timestamp=datetime.now(UTC),
        ),
    )

    assert await _events_of(bot_session, user_id, EventType.BOT_MUTED) == 1


async def test_unmute_is_recorded(client: BotClient, bot_session: AsyncSession) -> None:
    user_id = await _started(bot_session, client)

    await _feed(
        client,
        DialogUnmuted(
            chat_id=client.chat.chat_id,
            user=client.user,
            timestamp=datetime.now(UTC),
        ),
    )

    assert await _events_of(bot_session, user_id, EventType.BOT_UNMUTED) == 1


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
    # исполнитель не сотрудник: ни домов для привязки, ни кода
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
    # заблокированному жителю окно кода не положено: bind_by_code проверяет
    # только код, и с ним он привязал бы чат
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


async def test_a_mini_app_upsert_keeps_the_stop_mark(session: AsyncSession) -> None:
    # запрос мини-аппа не доказывает, что личный диалог с ботом снова жив
    repo = UsersRepo(session)
    max_user_id = _max_id()
    await repo.upsert_by_max_id(max_user_id, "Житель", None, MaxChatId(777))
    await repo.set_bot_stopped(max_user_id, datetime.now(UTC))

    user = await repo.upsert_by_max_id(max_user_id, "Житель", None, None)

    assert user.bot_stopped_at is not None


FIRST_SLOT = InlineButtonTextLocator("10:00")
ACCESS_REASON = "Поверка газового оборудования"


async def _access_window(
    session: AsyncSession,
    client: BotClient,
    broker: InMemoryBroker,
) -> tuple[AccessRequestId, AccessSlotId, FlatId]:
    # двум квартирам одно окно на одного: вторая займет его, пока у первой
    # висит клавиатура
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
    day = datetime.combine(request.date, time(10), tzinfo=UTC)
    [slot, _] = await access.add_slots(
        AccessRequestId(request.id),
        [(day, 1), (day + timedelta(hours=1), 1)],
    )
    await access.add_targets(
        AccessRequestId(request.id),
        [FlatId(mine.id), FlatId(other.id)],
    )
    ids = AccessRequestId(request.id), AccessSlotId(slot.id), FlatId(other.id)
    await session.commit()
    await _run(broker, broadcast_access_request, access_request_id=ids[0])
    return ids


async def test_the_access_window_is_sent_to_the_resident(
    client: BotClient,
    task_broker: InMemoryBroker,
    bot_session: AsyncSession,
    shows: list[Show],
) -> None:
    await _access_window(bot_session, client, task_broker)

    mode, _, chat_id, _ = _shown(shows, ACCESS_REASON)
    assert mode is ShowMode.SEND
    assert chat_id == client.chat.chat_id


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
) -> None:
    await _access_window(bot_session, client, task_broker)

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
