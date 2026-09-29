import asyncio
import json
import logging
import re
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from html import escape
from typing import Any, BinaryIO, cast
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from dishka import AsyncContainer
from maxo import Bot, Router
from maxo.dialogs import BgManagerFactory, ShowMode, StartMode
from maxo.dialogs.api.entities import DEFAULT_STACK_ID, NewMessage
from maxo.dialogs.context.media_storage import MediaIdStorage
from maxo.dialogs.test_tools import BotClient, MockMessageManager
from maxo.dialogs.test_tools.bot_client import FakeBot
from maxo.dialogs.test_tools.keyboard import InlineButtonTextLocator
from maxo.enums import ChatStatus as MaxChatStatus, ChatType, MessageLinkType
from maxo.errors import (
    MaxBotForbiddenError,
    MaxBotNetworkError,
    MaxBotNotFoundError,
    MaxBotTooManyRequestsError,
)
from maxo.omit import Omittable, Omitted
from maxo.routing.filters import Command
from maxo.routing.signals import MaxoUpdate
from maxo.types import (
    AudioAttachment,
    BotAddedToChat,
    BotCommand,
    BotRemovedFromChat,
    BotStarted,
    BotStopped,
    Callback,
    ClipboardButton,
    DialogMuted,
    DialogUnmuted,
    GetPinnedMessageResult,
    LocationAttachment,
    MediaAttachmentPayload,
    Message,
    MessageBody,
    MessageCallback,
    MessageCreated,
    MessageRemoved,
    NewMessageLink,
    OpenAppButton,
    PhotoAttachment,
    PhotoAttachmentPayload,
    Recipient,
    RequestGeoLocationButton,
    SendMessageResult,
    UserAddedToChat,
    VideoAttachment,
    VideoAttachmentDetails,
    VideoUrls,
)
from maxo.types.chat import Chat as MaxChat
from maxo.types.link_button import LinkButton
from maxo.types.simple_query_result import SimpleQueryResult
from maxo.types.user import User as MaxUser
from maxo.utils.deeplink import create_start_link, create_startapp_link
from maxo.utils.link import id_to_message_url
from maxo.utils.payload import decode_payload
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from taskiq import InMemoryBroker

from tests.conftest import PROBE_ROUTERS, RecordingBroker, photo_name

from zheka.bot import BotSetup
from zheka.bot.cards import VotePayload, app_payload
from zheka.bot.dialog_data import MeterPhotoData, NewRequestData
from zheka.bot.handlers.access.handlers import PICKED
from zheka.bot.handlers.access.windows import GONE_TEXT
from zheka.bot.handlers.chats.handlers import BOUND_TEXT, NO_RIGHTS_YET
from zheka.bot.handlers.chats.router import JOIN_TO_VOTE, UNPINNED, VOTE_UNWEIGHTED
from zheka.bot.handlers.chats.windows import CODE_TEXT, HOUSE_TEXT, RIGHTS_TEXT
from zheka.bot.handlers.commands.deeplinks import (
    APP_BUTTON,
    DEMO_ADMIN_NOTICE,
    DEMO_EXECUTOR_NOTICE,
    DEMO_RESIDENT_NOTICE,
    DEMO_STAFF_NOTICE,
    EXECUTOR_JOINED,
    ORG_JOINED,
    REGISTER_BUTTON,
    REGISTER_NOTICE,
)
from zheka.bot.handlers.commands.start import (
    BOT_COMMANDS,
    CHAT_COMMANDS_ONLY,
    DEMO_REMINDERS_TEXT,
    set_commands_handler,
)
from zheka.bot.handlers.consent.windows import GIVEN_TEXT
from zheka.bot.handlers.errors.router import UNEXPECTED
from zheka.bot.handlers.executor.handlers import DECLINE_SENT, PHOTO_TAKEN
from zheka.bot.handlers.executor.windows import (
    DECLINE_TEXT,
    NOT_YOURS_TEXT,
    RESULT_PHOTO_TEXT,
)
from zheka.bot.handlers.fallback import NOT_UNDERSTOOD
from zheka.bot.handlers.forget.handlers import FORGOTTEN_TEXT
from zheka.bot.handlers.menu.windows import (
    CALL_NOTE_TEXT,
    EMERGENCY_PHONE_TEXT,
    EMERGENCY_TEXT,
    GREETING,
    HOUSE_MENU_TEXT,
    MENU_TEXT,
    STAFF_TEXT,
)
from zheka.bot.handlers.meter_photo.handlers import ANOMALY_TEXT
from zheka.bot.handlers.meter_photo.windows import (
    MANUAL_TEXT as METER_MANUAL_TEXT,
    UNREADABLE_TEXT as METER_UNREADABLE_TEXT,
    WAIT_TEXT as METER_WAIT_TEXT,
)
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
from zheka.bot.handlers.question.handlers import ANSWER_SENT
from zheka.bot.handlers.question.windows import ANSWER, ANSWER_TEXT
from zheka.bot.handlers.requests.handlers import (
    NOT_CREATED,
    NOT_CREATED_UNEXPECTED,
    SENT_TEXT,
)
from zheka.bot.handlers.requests.windows import (
    ATTACHMENTS_TEXT,
    CANCEL_TEXT,
    CATEGORY_TEXT,
    CONFIRM_TEXT,
    CREATED_TEXT,
    DESCRIPTION_ATTACHMENTS_TEXT,
    DESCRIPTION_TEXT,
    IN_FLAT,
    IN_HOUSE,
    NOT_CONNECTED_TEXT,
    NO_HOUSE_TEXT,
    PLACE_TEXT,
    PROBLEM_TEXT,
    WORKS_TEXT,
)
from zheka.bot.handlers.review.handlers import REJECTION_TAKEN, repeat_sent
from zheka.bot.handlers.review.windows import (
    ASK_TEXT,
    OPTIONAL_PHOTO_TEXT,
    PHOTOS_TEXT,
    RATED_TEXT,
    REJECTION_PHOTO_TEXT,
    REJECTION_TEXT,
)
from zheka.bot.message_manager import ZhekaMessageManager
from zheka.bot.states import Consent, Menu
from zheka.bot.voice import VOICE_FAILED, VOICE_PENDING
from zheka.broker.task_names import TaskName
from zheka.broker.tasks import bot_requests, meters as meter_tasks
from zheka.broker.tasks.bot_requests import (
    NOT_REJECTED_UNEXPECTED,
    create_bot_request,
    reject_bot_request,
    transcribe_voice,
)
from zheka.broker.tasks.chats import (
    JOIN_HOUSE,
    LEFT_TEXT,
    PINS_HERE,
    WELCOME_MEMBER_TEXT,
    on_bot_added,
    sync_chat_card,
    sync_chat_pins,
    welcome_chat,
)
from zheka.broker.tasks.meters import recognize_meter_photo
from zheka.broker.tasks.notifications import (
    broadcast_to_chats,
    broadcast_to_users,
    send_register_pdf,
    send_to_user,
)
from zheka.broker.tasks.reminders import broadcast_access_request
from zheka.broker.tasks.requests import (
    attach_result_photo,
    send_executor_card,
    send_gji_pdf,
    send_question_card,
    send_review_card,
)
from zheka.core import texts
from zheka.core.consent import CONSENT_TEXT, CONSENT_VERSION
from zheka.core.deeplinks import (
    DeeplinkKind,
    chairman_payload,
    entrance_qr_payload,
    house_payload,
    org_invite_payload,
)
from zheka.core.enums import (
    CATEGORY_RULES,
    ChatCardKind,
    ChatStatus,
    DangerKind,
    EventSource,
    EventType,
    MeterType,
    NoticeStatus,
    NotificationCategory,
    NotificationLevel,
    OrgRole,
    RequestAttachmentKind,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestPlace,
    RequestStatus,
    ResidentRole,
    ResidentStatus,
    TariffZone,
)
from zheka.core.errors import HOUSE_NOT_FOUND, NotEnoughRights
from zheka.core.ids import (
    AccessRequestId,
    AccessSlotId,
    AnnouncementId,
    FlatId,
    HouseId,
    MaxChatId,
    MaxUserId,
    MeterId,
    OrgId,
    PollId,
    PollOptionId,
    RequestGroupId,
    RequestId,
    UserId,
)
from zheka.core.models import ChairmanHandover, User
from zheka.core.services.access import SLOT_FULL
from zheka.core.services.admin_requests import NO_DEMO_REQUEST
from zheka.core.services.chairman import NOT_A_NEIGHBOUR
from zheka.core.services.chats import (
    CHAT_NOT_BOUND,
    CHAT_TAKEN,
    PINS_TITLE,
    UNPIN_HINT,
    WRONG_CODE,
)
from zheka.core.services.demo import (
    CHECKER_RESERVED,
    DEMO_INNS,
    NOT_SEEDED,
    demo_flat_number,
)
from zheka.core.services.events import EventsService
from zheka.core.services.meter_photo import NOT_VERIFIED
from zheka.core.services.polls import ALREADY_VOTED
from zheka.core.services.profile import ProfileService
from zheka.core.services.reminders import DEMO_ADDRESS, DEMO_SERIAL
from zheka.core.services.requests import (
    CANCEL_TOO_LATE,
    MAX_RATING,
    MIN_RATING,
    REJECT_NOT_ON_REVIEW,
    RequestsService,
)
from zheka.core.texts import (
    CABINET_BUTTON,
    DANGER_REQUEST_NOTE,
    DANGER_TEXTS,
    DIGEST_BUTTON,
    DIGEST_EMPTY,
    DIGEST_SUBSCRIBE,
    DIGEST_SUBSCRIBED,
    ME_TOO,
    NO_EMERGENCY_PHONE_TEXT,
    OPEN_REQUEST,
    ORG_PHONE_TEXT,
    REQUEST_PLACE_LINES,
    REQUEST_STATUS_LABELS,
    VOTE,
    VOTE_IN_APP,
    danger_warning,
)
from zheka.infra.database.models import (
    Announcement,
    Chat,
    ChatCard,
    ChatPin,
    Flat,
    House,
    NoticeDelivery,
    OrgInvite,
    OrgMember,
    Organization,
    Request,
    RequestMessage,
    Resident,
)
from zheka.infra.database.repos.access import AccessRepo
from zheka.infra.database.repos.chairman import ChairmanRepo
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.notifications import NotificationsRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import FORGOTTEN_NAME, UsersRepo
from zheka.infra.database.tables.access import access_targets_table
from zheka.infra.database.tables.announcements import (
    announcements_table,
    notice_deliveries_table,
)
from zheka.infra.database.tables.chats import chat_cards_table
from zheka.infra.database.tables.events import events_table
from zheka.infra.database.tables.houses import houses_table
from zheka.infra.database.tables.organizations import org_members_table
from zheka.infra.database.tables.requests import requests_table
from zheka.infra.database.tables.residents import residents_table
from zheka.infra.database.tables.users import users_table
from zheka.infra.max import MaxSender
from zheka.infra.max.sender import _chat_rate_limit, dialog_notify, is_chat_admin
from zheka.infra.pdf import PdfDocument
from zheka.infra.yandex import SpeechClient, YandexQuota
from zheka.infra.yandex.vision import VisionClient


class _RecordingBot(FakeBot):
    def __init__(self) -> None:
        super().__init__()
        self.notifies: list[bool] = []
        self.texts: list[str | None] = []
        self.chat_ids: list[Any] = []
        self.links: list[Any] = []
        self.buttons: list[list[Any]] = []

    async def send_message(  # type: ignore[mutable-override]
        self,
        *_: Any,
        **kwargs: Any,
    ) -> SendMessageResult:
        self.notifies.append(kwargs["notify"])
        self.texts.append(kwargs.get("text"))
        self.chat_ids.append(kwargs.get("chat_id"))
        self.links.append(kwargs.get("link"))
        self.buttons.append(
            [
                button
                for attachment in kwargs.get("attachments") or []
                for row in attachment.payload.buttons
                for button in row
            ],
        )
        return SendMessageResult(
            message=Message(
                recipient=Recipient(chat_type=ChatType.DIALOG, chat_id=1),
                timestamp=datetime.now(UTC),
                body=MessageBody(mid="1", seq=1, text=kwargs.get("text")),
            ),
        )


ACCEPT = InlineButtonTextLocator("✅ Даю согласие")
NEW_REQUEST = InlineButtonTextLocator("📝 Подать заявку")
FIRST_CATEGORY = InlineButtonTextLocator(
    CATEGORY_RULES[next(iter(RequestCategory))].caption,
)
NEXT = InlineButtonTextLocator("➡️ Дальше")
SEND = InlineButtonTextLocator("📨 Отправить")
TO_MENU = InlineButtonTextLocator("🏠 Меню")
SEND_READING = InlineButtonTextLocator("✅ Отправить")
SEND_ANYWAY = InlineButtonTextLocator("✅ Всё верно, отправить")
EDIT_READING = InlineButtonTextLocator("✏️ Исправить")


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


async def _user(session: AsyncSession, client: BotClient) -> User:
    user = await UsersRepo(session).get_by_max_id(MaxUserId(client.user.id))
    assert user is not None
    return user


async def test_a_message_from_a_house_chat_starts_nothing(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    message_manager: MockMessageManager,
) -> None:
    message_manager.reset_history()
    max_user_id = _max_id()
    group = _in_chat(bot_setup, fake_bot, MaxChatId(max_user_id), max_user_id)

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
    window = NewMessage(recipient=Recipient(chat_type=ChatType.DIALOG), text="Окно")

    await manager.send_message(recorder, window)
    assert recorder.notifies == [False]

    token = dialog_notify.set(True)
    try:
        await manager.send_message(recorder, window)
    finally:
        dialog_notify.reset(token)
    assert recorder.notifies == [False, True]


async def test_start_dialog_returns_with_the_window_sent_and_the_name_kept(
    client: BotClient,
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await client.send("/start")
    user = await _user(bot_session, client)
    name = user.name
    message_manager.reset_history()
    sender = MaxSender(fake_bot, bot_setup.bg_manager_factory)

    await sender.start_dialog(Menu.main, user, notify=False)

    assert message_manager.sent_messages != []
    bot_session.expire_all()
    assert (await _user(bot_session, client)).name == name


async def test_a_tap_on_a_dead_window_restarts_the_menu(
    client: BotClient,
    message_manager: MockMessageManager,
) -> None:
    await client.send("/start")
    stale = message_manager.last_message()
    await client.send("/start")
    message_manager.reset_history()

    await client.click(stale, ACCEPT)

    await _rendered(message_manager, MENU_TEXT)


async def test_the_start_is_recorded_once_and_a_loose_message_is_not_a_start(
    client: BotClient,
    bot_session: AsyncSession,
) -> None:
    await client.send("здравствуйте")
    await client.send("/start")

    assert await _starts_of(bot_session, client) == [{"source": "direct"}]


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
    group = _in_chat(bot_setup, fake_bot, MaxChatId(max_user_id), max_user_id)

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
    outside = _in_chat(bot_setup, recorder, _chat_id(), _max_id())

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
    org_id: OrgId | None = None,
) -> tuple[HouseId, str]:
    house = House(
        timezone="Europe/Moscow",
        org_id=org_id,
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


async def _starts_of(session: AsyncSession, client: BotClient) -> list[Any]:
    stmt = select(events_table.c.payload).where(
        events_table.c.type == EventType.BOT_START,
        events_table.c.user_id.in_(
            select(users_table.c.id).where(users_table.c.max_user_id == client.user.id),
        ),
    )
    return list((await session.execute(stmt)).scalars())


@pytest.mark.parametrize(
    "payload",
    ["не-диплинк", Omitted()],
)
async def test_a_start_without_a_deeplink_falls_through_to_start(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    payload: Omittable[str | None],
) -> None:
    await _bot_started(client, payload)

    assert message_manager.sent_messages
    assert CONSENT_TEXT in _text(message_manager)
    assert await _starts_of(bot_session, client) == [{"source": "direct"}]


async def _linked(
    session: AsyncSession,
    client: BotClient,
    house_id: HouseId,
    created_at: datetime,
) -> None:
    user = await _user(session, client)
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
    address = _text(message_manager)
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
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
    await _consented(client, message_manager)
    now = datetime.now(UTC)
    _, first = await _org_house(bot_session)
    last, address = await _bot_house(bot_session, org_id=await _org(bot_session))
    await _linked(bot_session, client, first, now)
    await _linked(bot_session, client, last, now + timedelta(minutes=1))

    assert address in await _draft_request(client, message_manager)
    enqueued = bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)
    assert enqueued[-1]["house_id"] == int(last)
    await client.click(message_manager.last_message(), TO_MENU)
    assert HOUSE_MENU_TEXT.format(address=address) in _text(message_manager)


DEPART = InlineButtonTextLocator("🚗 Выехал")
READY = InlineButtonTextLocator("🏁 Готово")
RIGHTS_DONE = InlineButtonTextLocator("✅ Готово")
REJECT = InlineButtonTextLocator("👎 Сделано плохо")
RESULT_URL = "https://max.ru/result.jpg"
PHOTO_TOKEN = "photo-token"  # noqa: S105


async def _org_house(session: AsyncSession) -> tuple[OrgId, HouseId]:
    org_id = await _org(session)
    house_id, _ = await _bot_house(session, org_id=org_id)
    return org_id, house_id


async def _started(session: AsyncSession, client: BotClient) -> UserId:
    await client.send("/start")
    return (await _user(session, client)).id


async def _request(
    session: AsyncSession,
    house_id: HouseId,
    status: RequestStatus,
    *,
    author: UserId | None = None,
    executor: UserId | None = None,
    flat: FlatId | None = None,
) -> RequestId:
    request = Request(
        house_id=house_id,
        flat_id=flat,
        author_user_id=author,
        executor_user_id=executor,
        category=RequestCategory.LEAK,
        description="Течет кран",
        status=status,
        channel=RequestChannel.MINIAPP,
        reviewed_at=datetime.now(UTC) if status is RequestStatus.ON_REVIEW else None,
        deadline_at=datetime.now(UTC),
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
    house_id = await _staff(session, client, OrgRole.EXECUTOR)
    executor = (await _user(session, client)).id
    return await _request(session, house_id, status, executor=executor)


async def _run(broker: InMemoryBroker, task: Any, **kwargs: Any) -> None:
    sent = await task.kicker().with_broker(broker).kiq(**kwargs)
    result = await sent.wait_result(timeout=5)
    assert not result.is_err, result.error


async def _status(session: AsyncSession, request_id: RequestId) -> Request:
    session.expire_all()
    request = await RequestsRepo(session).get(request_id)
    assert request is not None
    return request


async def _send(client: BotClient, attachment: Any) -> None:
    message = Message(
        sender=client.user,
        recipient=Recipient(chat_type=ChatType.DIALOG, chat_id=client.chat.chat_id),
        timestamp=datetime.now(UTC),
        body=MessageBody(
            mid=secrets.token_hex(4),
            seq=1,
            text=None,
            attachments=[attachment],
        ),
    )
    await _feed(client, MessageCreated(message=message, timestamp=datetime.now(UTC)))


async def _rendered(message_manager: MockMessageManager, text: str) -> None:
    async with asyncio.timeout(5):
        while not message_manager.sent_messages or text not in (  # noqa: ASYNC110
            _text(message_manager)
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
    assert CANCEL.find_button(message_manager.last_message()) is not None

    photo = PhotoAttachmentPayload(photo_id=1, token=PHOTO_TOKEN, url=RESULT_URL)
    await _send(client, PhotoAttachment(payload=photo))

    assert bot_broker.enqueued(TaskName.ATTACH_RESULT_PHOTO)[-1] == {
        "user_id": request.executor_user_id,
        "request_id": request_id,
        "photo_urls": [RESULT_URL],
    }
    assert MENU_TEXT in _text(message_manager)
    assert PHOTO_TAKEN in notices.texts


async def test_a_rejection_on_the_review_card_opens_a_repeat_from_the_bot(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
    shows: list[Show],
    notices: _RecordingBot,
) -> None:
    request_id = await _reviewing(bot_session, client, task_broker)
    mode, _, chat_id, _ = shows[-1]
    assert mode is ShowMode.SEND
    assert chat_id == client.chat.chat_id
    assert _opened(_buttons(message_manager.last_message())) == [
        (OPEN_REQUEST, f"/requests/{request_id}"),
    ]

    await client.click(message_manager.last_message(), REJECT)
    await _rendered(message_manager, REJECTION_TEXT)
    await client.send("Кран все еще течет")
    assert _text(message_manager) == REJECTION_PHOTO_TEXT
    assert SEND.find_button(message_manager.last_message()) is None
    await _send_photo(client, None)
    assert PHOTOS_TEXT.format(photos=1) in _text(message_manager)
    await client.click(message_manager.last_message(), SEND)

    assert REJECTION_TAKEN in notices.texts
    assert GREETING in _text(message_manager)
    kwargs = bot_broker.enqueued(TaskName.REJECT_BOT_REQUEST)[-1]
    assert kwargs["comment"] == "Кран все еще течет"
    assert kwargs["photo_urls"] == [RESULT_URL]
    download = AsyncMock(
        side_effect=lambda _url, out, **_: out.write(b"\xff\xd8\xff\xe0"),
    )
    monkeypatch.setattr(fake_bot, "download", download)
    await _run(task_broker, reject_bot_request, **kwargs)

    parent = await _status(bot_session, request_id)
    assert parent.completion_reason is RequestCompletionReason.RESIDENT_REJECTED
    [repeat] = await _repeats_of(bot_session, request_id)
    assert repeat.channel is RequestChannel.BOT
    assert repeat.description == "Кран все еще течет"
    [photo] = await RequestsRepo(bot_session).list_attachments(repeat.id)
    assert photo.kind is RequestAttachmentKind.ISSUE
    sent = bot_broker.enqueued(TaskName.SEND_TO_USER)[-1]
    assert sent["text"] == repeat_sent(repeat.id)
    assert (sent["app_button"], sent["app_path"]) == (
        OPEN_REQUEST,
        f"/requests/{repeat.id}",
    )


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
    bot_broker: RecordingBroker,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    download = AsyncMock(
        side_effect=lambda _url, out, **_: out.write(b"\xff\xd8\xff\xe0"),
    )
    monkeypatch.setattr(fake_bot, "download", download)
    request_id = await _reviewing(bot_session, client, task_broker)
    card = message_manager.last_message()
    await client.click(card, REJECT)
    await _rendered(message_manager, REJECTION_TEXT)
    await client.click(card, ACCEPT_WORK)

    await _send_photo(client, "Спасибо, все хорошо")
    await client.click(message_manager.last_message(), SEND)
    await _run(
        task_broker,
        reject_bot_request,
        **bot_broker.enqueued(TaskName.REJECT_BOT_REQUEST)[-1],
    )

    assert await _repeats_of(bot_session, request_id) == []
    assert GREETING in _text(message_manager)
    sent = bot_broker.enqueued(TaskName.SEND_TO_USER)[-1]
    assert REJECT_NOT_ON_REVIEW in sent["text"]
    assert sent["app_path"] == f"/requests/{request_id}"


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

    assert NOT_YOURS_TEXT.format(request_id=request_id) in (_text(message_manager))


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

    text = _text(message_manager)
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

    assert RATED_TEXT.format(rating=MIN_RATING) in (_text(message_manager))


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
    assert NOT_YOURS_TEXT.format(request_id=request_id) in (text or "")
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
    await _bot_stopped(client)
    assert (await _user(bot_session, client)).bot_stopped_at is not None

    await client.send("/start")

    bot_session.expire_all()
    assert (await _user(bot_session, client)).bot_stopped_at is None


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


async def _staff(
    session: AsyncSession,
    client: BotClient,
    role: OrgRole = OrgRole.ADMIN,
) -> HouseId:
    user_id = await _started(session, client)
    org_id, house_id = await _org_house(session)
    session.add(OrgMember(org_id=org_id, user_id=user_id, role=role))
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
    house_button = InlineButtonTextLocator(re.escape(f"🏢 {house.street_address}"))
    await client.click(window, house_button)
    await client.click(message_manager.last_message(), RIGHTS_DONE)
    assert NO_RIGHTS_YET in _text(message_manager)
    chat_api.is_admin = True
    await client.click(message_manager.last_message(), RIGHTS_DONE)

    text = _text(message_manager)
    assert BOUND_TEXT.format(title=CHAT_TITLE) in text
    assert GREETING not in text
    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None
    assert chat.house_id == house_id
    assert chat.bot_is_admin is True
    assert bot_broker.enqueued(TaskName.WELCOME_CHAT)[-1] == {
        "chat_id": chat_id,
        "house_id": house_id,
        "member": None,
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
    chat_id, code, house_id = await _code_window(bot_session, client, task_broker)
    assert CODE_TEXT.format(title=CHAT_TITLE) in _text(message_manager)
    assert _shown(shows, CODE_TEXT.format(title=CHAT_TITLE))[0] is ShowMode.SEND
    assert CANCEL.find_button(message_manager.last_message()) is not None
    await client.send("не тот код")
    assert WRONG_CODE in _text(message_manager)
    await client.send(code)
    chat_api.is_admin = True
    await client.click(message_manager.last_message(), RIGHTS_DONE)

    assert GREETING in _text(message_manager)
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
    stranger = BotClient(bot_setup.dp, user_id=_max_id(), bot=fake_bot)
    chat_id = _chat_id()

    await _feed(
        stranger,
        BotAddedToChat(
            chat_id=chat_id,
            is_channel=False,
            user=stranger.user,
            timestamp=datetime.now(UTC),
        ),
    )

    users = UsersRepo(bot_session)
    assert await users.get_by_max_id(MaxUserId(stranger.user.id)) is None
    assert bot_broker.enqueued(TaskName.ON_BOT_ADDED)[-1] == {
        "chat_id": chat_id,
        "is_channel": False,
        "initiator_max_user_id": stranger.user.id,
    }


async def test_a_bot_that_is_no_longer_in_the_chat_is_not_its_admin(
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fake_bot, "get_membership", _forbidden)

    assert await is_chat_admin(fake_bot, _chat_id()) is False


async def _member_added(
    client: BotClient,
    chat_id: MaxChatId,
    *,
    is_bot: bool = False,
) -> BotClient:
    member = BotClient(client.dp, user_id=_max_id(), bot=client.bot)
    user = MaxUser(user_id=member.user.id, first_name="Анна <3", is_bot=is_bot)
    await _feed(
        member,
        UserAddedToChat(
            chat_id=chat_id,
            is_channel=False,
            user=user,
            timestamp=datetime.now(UTC),
        ),
    )
    return member


def _welcomes(broker: RecordingBroker, chat_id: MaxChatId) -> list[dict[str, Any]]:
    return [
        task
        for task in broker.enqueued(TaskName.WELCOME_CHAT)
        if task["chat_id"] == chat_id
    ]


async def test_a_member_added_to_a_bound_chat_is_welcomed_by_name(
    client: BotClient,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    chat_id = await _bound_chat(bot_session, client)
    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None

    member = await _member_added(client, chat_id)
    await _member_added(client, chat_id, is_bot=True)

    assert _welcomes(bot_broker, chat_id) == [
        {"chat_id": chat_id, "house_id": chat.house_id, "member": "Анна <3"},
    ]
    assert await UsersRepo(bot_session).get_by_max_id(MaxUserId(member.user.id)) is None


async def test_a_member_added_to_an_unbound_chat_is_not_welcomed(
    client: BotClient,
    bot_broker: RecordingBroker,
) -> None:
    chat_id = _chat_id()

    await _member_added(client, chat_id)

    assert _welcomes(bot_broker, chat_id) == []


async def test_the_member_welcome_escapes_the_name(
    task_broker: InMemoryBroker,
    notices: _RecordingBot,
) -> None:
    task: Any = welcome_chat
    sent = (
        await task.kicker()
        .with_broker(task_broker)
        .kiq(
            chat_id=_chat_id(),
            house_id=1,
            member="Анна <3",
        )
    )
    result = await sent.wait_result(timeout=5)
    assert not result.is_err, result.error

    assert notices.texts == [WELCOME_MEMBER_TEXT.format(name="Анна &lt;3")]


async def _bound_chat(session: AsyncSession, client: BotClient) -> MaxChatId:
    house_id = await _staff(session, client)
    user = await _user(session, client)
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
    monkeypatch.setattr(fake_bot, "send_message", _forbidden)


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
@pytest.mark.parametrize("is_admin", [False, True])
async def test_a_failed_chat_send_asks_the_binder_only_for_lost_rights(
    client: BotClient,
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
    shows: list[Show],
    is_admin: bool,
) -> None:
    chat_api.is_admin = is_admin
    chat_id = await _bound_chat(bot_session, client)

    assert await _broadcast(task_broker, chat_id) == 0

    bot_session.expire_all()
    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None
    assert chat.bot_is_admin is is_admin
    rights = RIGHTS_TEXT.format(title=CHAT_TITLE)
    asked = [
        (mode, to, sound) for mode, text, to, sound in shows if rights in (text or "")
    ]
    assert asked == ([] if is_admin else [(ShowMode.SEND, client.chat.chat_id, True)])


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
) -> tuple[MaxChatId, str, HouseId]:
    user_id = await _started(session, client)
    _, house_id = await _org_house(session)
    session.add(Resident(user_id=user_id, house_id=house_id, role=ResidentRole.OWNER))
    await session.commit()
    house = await HousesRepo(session).get(house_id)
    assert house is not None
    code = house.chat_binding_code
    chat_id = _chat_id()
    await _added_by(broker, chat_id, initiator_max_user_id=client.user.id)
    return chat_id, code, house_id


@pytest.mark.usefixtures("chat_api")
async def test_a_code_for_a_chat_the_bot_left_ends_on_the_menu(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    chat_id, code, _ = await _code_window(bot_session, client, task_broker)
    await _bot_removed(client, chat_id)
    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None
    assert chat.status == ChatStatus.REMOVED

    await client.send(code)

    assert GREETING in _text(message_manager)
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
    chat_id, code, _ = await _code_window(bot_session, client, task_broker)
    await client.send(code)
    await _bot_removed(client, chat_id)
    shows.clear()

    await client.click(message_manager.last_message(), RIGHTS_DONE)

    assert _shown(shows, GREETING)[0] is ShowMode.SEND
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


async def test_the_bot_leaves_a_chat_added_by_an_executor(
    client: BotClient,
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    await _staff(bot_session, client, OrgRole.EXECUTOR)
    chat_id = _chat_id()

    await _added_by(task_broker, chat_id, initiator_max_user_id=client.user.id)

    assert chat_api.left == [chat_id]
    assert notices.texts == [LEFT_TEXT.format(title=CHAT_TITLE)]


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


async def test_a_refused_access_window_renders_the_escaped_refusal(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _access_window(bot_session, client, task_broker)
    window = message_manager.last_message()
    stmt = (
        update(residents_table)
        .where(residents_table.c.user_id == (await _user(bot_session, client)).id)
        .values(status=ResidentStatus.BLOCKED, block_reason="долг <3 мес>")
    )
    await bot_session.execute(stmt)
    await bot_session.commit()

    await client.click(window, FIRST_SLOT)

    assert GONE_TEXT in _text(message_manager)
    assert "долг &lt;3 мес&gt;" in _text(message_manager)


async def _bot_demo(session: AsyncSession, number: int = 1) -> tuple[OrgId, str]:
    inn = DEMO_INNS[number - 1]
    org = await OrgsRepo(session).get_by_inn(inn)
    if org is not None:
        houses = await HousesRepo(session).list_for_org(org.id)
        return org.id, houses[0].address
    org_id = await _org(session, name=f"Демо-УК «{number}»", inn=inn, is_demo=True)
    _, address = await _bot_house(
        session,
        city="Демоград",
        street="Демо",
        building=str(number),
        org_id=org_id,
    )
    return org_id, address


async def _demo_roles(
    session: AsyncSession,
    client: BotClient,
) -> tuple[list[tuple[OrgId, OrgRole]], list[HouseId]]:
    user = await _user(session, client)
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


async def test_a_demo_resident_link_gives_only_a_flat_in_its_organization(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    org_id, address = await _bot_demo(bot_session, 2)
    await _consented(client, message_manager)

    await _bot_started(client, "demo_resident_2")

    user = await _user(bot_session, client)
    assert HOUSE_MENU_TEXT.format(address=address) in _text(message_manager)
    assert (
        DEMO_RESIDENT_NOTICE.format(
            flat=demo_flat_number(user.id),
            address=address,
            org="Демо-УК «2»",
        )
        in notices.texts
    )
    assert _opened(notices.buttons[-1]) == [(APP_BUTTON, None)]
    houses = await HousesRepo(bot_session).list_for_org(org_id)
    assert await _demo_roles(bot_session, client) == ([], [houses[0].id])
    starts = await _starts_of(bot_session, client)
    assert starts.count({"source": EventSource.DEEPLINK.value}) == 1


async def test_a_demo_link_without_consent_asks_for_it_and_then_grants_access(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    org_id, _address = await _bot_demo(bot_session)

    await _bot_started(client, "demo_staff_1")
    assert CONSENT_TEXT in _text(message_manager)
    await client.click(message_manager.last_message(), ACCEPT)

    assert MENU_TEXT in _text(message_manager)
    assert DEMO_STAFF_NOTICE.format(org="Демо-УК «1»") in notices.texts
    assert await _demo_roles(bot_session, client) == (
        [(org_id, OrgRole.EMPLOYEE)],
        [],
    )
    assert await _starts_of(bot_session, client) == [{"source": "deeplink"}]


async def test_a_demo_staff_link_lowers_a_demo_admin_to_an_employee(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    org_id, _address = await _bot_demo(bot_session, 3)
    await _consented(client, message_manager)

    await _bot_started(client, "demo_admin_3")
    assert MENU_TEXT in _text(message_manager)
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
    await _consented(client, message_manager)
    house_id, address = await _bot_house(bot_session)
    await _linked(bot_session, client, house_id, datetime.now(UTC))

    await client.click(message_manager.last_message(), NEW_REQUEST)

    assert NOT_CONNECTED_TEXT.format(address=address) in _text(message_manager)
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


async def test_the_welcome_carries_the_link_to_the_house(
    task_broker: InMemoryBroker,
    fake_bot: FakeBot,
    pin_api: _PinApi,
) -> None:
    chat_id = _chat_id()
    house_id = HouseId(secrets.randbits(20))

    await _run(task_broker, welcome_chat, chat_id=chat_id, house_id=house_id)

    [message] = pin_api.sent
    assert message["chat_id"] == chat_id
    assert message["notify"] is False
    assert message["text"].endswith("поиском: #объявление, #опрос, #заявка")
    [attachment] = message["attachments"]
    assert attachment.payload.buttons == _join_house(fake_bot, house_id)


async def _grouped_chat(
    session: AsyncSession,
    client: BotClient,
    status: RequestStatus = RequestStatus.NEW,
) -> tuple[MaxChatId, HouseId, RequestGroupId]:
    chat_id = await _bound_chat(session, client)
    chat = await ChatsRepo(session).get(chat_id)
    assert chat is not None
    assert chat.house_id is not None
    house_id = chat.house_id
    flats = [Flat(house_id=house_id, number=number) for number in ("5", "6")]
    session.add_all(flats)
    await session.flush()
    repo = RequestsRepo(session)
    group = await repo.create_group(house_id, RequestCategory.LEAK, datetime.now(UTC))
    requests = [
        Request(
            house_id=house_id,
            flat_id=flat.id,
            category=RequestCategory.LEAK,
            description="Течет стояк",
            status=status,
            channel=RequestChannel.MINIAPP,
            deadline_at=datetime.now(UTC),
            group_id=group.id,
        )
        for flat in flats
    ]
    session.add_all(requests)
    await session.flush()
    group_id = group.id
    await session.commit()
    return chat_id, house_id, group_id


async def _cards(session: AsyncSession, chat_id: MaxChatId) -> list[str]:
    session.expire_all()
    stmt = select(chat_cards_table.c.mid).where(chat_cards_table.c.chat_id == chat_id)
    return list((await session.execute(stmt)).scalars().all())


async def test_the_group_card_is_posted_once_and_then_edited_in_place(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    fake_bot: FakeBot,
    bot_session: AsyncSession,
) -> None:
    chat_id, house_id, group_id = await _grouped_chat(bot_session, client)
    card = {"kind": ChatCardKind.GROUP, "ref_id": group_id}

    await _run(task_broker, sync_chat_card, **card, post=True)
    await _run(task_broker, sync_chat_card, **card, post=True)

    [sent] = pin_api.sent
    assert sent["chat_id"] == chat_id
    assert sent["notify"] is False
    assert sent["text"] == texts.group_card(RequestCategory.LEAK, 2, RequestStatus.NEW)
    [attachment] = sent["attachments"]
    me_too = create_startapp_link(fake_bot, f"house_{house_id}_leak")
    assert attachment.payload.buttons == [
        [LinkButton(text=ME_TOO, url=me_too)],
        *_join_house(fake_bot, house_id),
    ]
    [edited] = pin_api.edited
    assert edited["message_id"] == "list-1"
    assert await _cards(bot_session, chat_id) == ["list-1"]


async def test_a_status_sync_edits_only_a_posted_card(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
) -> None:
    chat_id, _, group_id = await _grouped_chat(bot_session, client)

    await _run(
        task_broker,
        sync_chat_card,
        kind=ChatCardKind.GROUP,
        ref_id=group_id,
        post=False,
    )

    assert pin_api.sent == []
    assert await _cards(bot_session, chat_id) == []


async def test_a_reviewed_group_card_says_done_and_drops_the_buttons(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
) -> None:
    chat_id, _, group_id = await _grouped_chat(
        bot_session,
        client,
        RequestStatus.ON_REVIEW,
    )
    bot_session.add(
        ChatCard(chat_id=chat_id, kind=ChatCardKind.GROUP, ref_id=group_id, mid="c-1"),
    )
    await bot_session.commit()

    await _run(
        task_broker,
        sync_chat_card,
        kind=ChatCardKind.GROUP,
        ref_id=group_id,
        post=False,
    )

    [edited] = pin_api.edited
    assert edited["message_id"] == "c-1"
    assert edited["text"] == texts.group_card_done(RequestCategory.LEAK, 2)
    assert edited["attachments"] == []


async def _polled_chat(
    session: AsyncSession,
    client: BotClient,
    *,
    is_multiple: bool = False,
) -> tuple[MaxChatId, PollId, list[PollOptionId]]:
    chat_id = await _bound_chat(session, client)
    chat = await ChatsRepo(session).get(chat_id)
    assert chat is not None
    assert chat.house_id is not None
    user = await _user(session, client)
    flat = Flat(house_id=chat.house_id, number="7", area=5000)
    session.add(flat)
    await session.flush()
    session.add(
        Resident(
            user_id=user.id,
            house_id=chat.house_id,
            flat_id=flat.id,
            role=ResidentRole.OWNER,
        ),
    )
    now = datetime.now(UTC)
    repo = PollsRepo(session)
    poll = await repo.create(
        chat.house_id,
        None,
        user.id,
        "staff",
        "Ставим шлагбаум?",
        None,
        is_multiple,
        now,
        now + timedelta(days=3),
        ["Да", "Нет"],
    )
    poll_id = poll.id
    options = [option.id for option in await repo.list_options(poll_id)]
    await session.commit()
    return chat_id, poll_id, options


class _CallbackAnswers:
    def __init__(self) -> None:
        self.notifications: list[str | None] = []

    async def answer_on_callback(self, **kwargs: Any) -> SimpleQueryResult:
        self.notifications.append(kwargs.get("notification"))
        return SimpleQueryResult(success=True)


@pytest.fixture
def answers(fake_bot: FakeBot, monkeypatch: pytest.MonkeyPatch) -> _CallbackAnswers:
    recorder = _CallbackAnswers()
    monkeypatch.setattr(fake_bot, "answer_on_callback", recorder.answer_on_callback)
    return recorder


async def _vote_tap(
    group: BotClient,
    chat_id: MaxChatId,
    poll_id: PollId,
    option_id: PollOptionId,
) -> None:
    await _feed(
        group,
        MessageCallback(
            timestamp=datetime.now(UTC),
            callback=Callback(
                callback_id=secrets.token_hex(4),
                timestamp=datetime.now(UTC),
                user=group.user,
                payload=VotePayload(poll_id=poll_id, option_id=option_id).pack(),
            ),
            message=_chat_message(chat_id, "card-1", 1),
        ),
    )


async def test_a_vote_tap_in_the_chat_votes_once_and_answers_with_a_toast(
    client: BotClient,
    bot_setup: BotSetup,
    fake_bot: FakeBot,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    answers: _CallbackAnswers,
) -> None:
    chat_id, poll_id, options = await _polled_chat(bot_session, client)
    group = _in_chat(bot_setup, fake_bot, chat_id, client.user.id)
    stranger = _in_chat(bot_setup, fake_bot, chat_id, _max_id())
    outsider_id = _max_id()
    bot_session.add(User(max_user_id=outsider_id, name="Гость"))
    await bot_session.commit()
    outsider = _in_chat(bot_setup, fake_bot, chat_id, outsider_id)

    await _vote_tap(stranger, chat_id, poll_id, options[0])
    await _vote_tap(outsider, chat_id, poll_id, options[0])
    await _vote_tap(group, chat_id, poll_id, options[0])
    await _vote_tap(group, chat_id, poll_id, options[1])

    assert answers.notifications == [
        JOIN_TO_VOTE,
        JOIN_TO_VOTE,
        VOTE_UNWEIGHTED,
        ALREADY_VOTED,
    ]
    user = await _user(bot_session, client)
    stmt = select(events_table.c.payload).where(
        events_table.c.type == EventType.POLL_VOTED,
        events_table.c.user_id == user.id,
    )
    assert (await bot_session.execute(stmt)).scalars().all() == [
        {
            "poll_id": poll_id,
            "source": "chat",
        },
    ]
    assert {
        "kind": "poll",
        "ref_id": poll_id,
        "post": False,
    } in bot_broker.enqueued(TaskName.SYNC_CHAT_CARD)


@pytest.mark.parametrize("is_multiple", [False, True])
async def test_the_poll_card_votes_by_buttons_only_with_one_answer(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
    is_multiple: bool,
) -> None:
    chat_id, poll_id, options = await _polled_chat(
        bot_session,
        client,
        is_multiple=is_multiple,
    )

    await _run(
        task_broker,
        sync_chat_card,
        kind=ChatCardKind.POLL,
        ref_id=poll_id,
        post=True,
    )

    [sent] = pin_api.sent
    assert sent["text"].startswith("🗳 Опрос УК: Ставим шлагбаум?\n1. Да - 0 кв., 0%")
    assert "Голосуют собственники, это не ОСС" in sent["text"]
    [attachment] = sent["attachments"]
    rows = attachment.payload.buttons
    if is_multiple:
        assert [button.text for button in rows[0]] == [VOTE_IN_APP]
    else:
        assert [row[0].payload for row in rows[:2]] == [
            VotePayload(poll_id=poll_id, option_id=option).pack() for option in options
        ]
    assert [button.text for button in rows[-1]] == [JOIN_HOUSE]
    assert await _cards(bot_session, chat_id) == ["list-1"]


async def test_a_chat_reminder_replies_to_the_poll_card(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
) -> None:
    chat_id, poll_id, _ = await _polled_chat(bot_session, client)
    bot_session.add(
        ChatCard(chat_id=chat_id, kind=ChatCardKind.POLL, ref_id=poll_id, mid="c-9"),
    )
    await bot_session.commit()

    await _run(
        task_broker,
        broadcast_to_chats,
        chat_ids=[chat_id],
        text="🗳 Идет опрос",
        card_kind=ChatCardKind.POLL,
        card_ref_id=poll_id,
    )

    [sent] = pin_api.sent
    assert sent["link"] == NewMessageLink(mid="c-9", type=MessageLinkType.REPLY)


async def _listed_chat(
    session: AsyncSession,
    client: BotClient,
    *texts: str | None,
    pins_mid: str | None = None,
) -> tuple[MaxChatId, HouseId]:
    chat_id = await _bound_chat(session, client)
    user = await _user(session, client)
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
    assert attachment.payload.buttons == _join_house(fake_bot, house_id)
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
    monkeypatch.setattr(fake_bot, failing, _forbidden)
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
        "resend": False,
    }
    assert recorder.texts == []


async def test_unpin_replies_in_the_chat_and_repin_answers_only_with_the_list(
    client: BotClient,
    bot_setup: BotSetup,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    chat_id, _ = await _listed_chat(bot_session, client, None, None)
    recorder = _RecordingBot()
    group = _in_chat(bot_setup, recorder, chat_id, client.user.id)

    await group.send("/unpin 2")
    await group.send("/unpin")
    synced = bot_broker.enqueued(TaskName.SYNC_CHAT_PINS)[-1]
    await group.send("/repin")

    assert await _pin_mids(bot_session, chat_id) == ["m-1"]
    assert recorder.texts == [UNPINNED, UNPIN_HINT]
    assert [link.type for link in recorder.links] == [MessageLinkType.REPLY] * 2
    assert synced == {"chat_id": chat_id, "notify": False, "resend": False}
    assert bot_broker.enqueued(TaskName.SYNC_CHAT_PINS)[-1] == {
        "chat_id": chat_id,
        "notify": False,
        "resend": True,
    }


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


@pytest.mark.parametrize("command", ["/pin", "/unpin", "/repin"])
async def test_a_chat_command_in_a_private_dialog_says_where_it_works(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    command: str,
) -> None:
    max_user_id = _max_id()
    recorder = _RecordingBot()
    client = BotClient(
        bot_setup.dp,
        user_id=max_user_id,
        chat_id=max_user_id,
        bot=recorder,
    )

    await client.send(command)

    assert recorder.texts == [CHAT_COMMANDS_ONLY]


async def test_deleting_the_list_message_in_the_chat_unpins_everything(
    client: BotClient,
    bot_session: AsyncSession,
) -> None:
    chat_id, _ = await _listed_chat(bot_session, client, None, None, pins_mid="list-1")

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
    fake_bot: FakeBot,
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
    assert [
        button.web_app
        for button in _buttons(message_manager.last_message())
        if isinstance(button, OpenAppButton)
    ] == [fake_bot.state.info.username]


async def test_the_policy_button_opens_the_privacy_page_of_the_mini_app(
    client: BotClient,
    message_manager: MockMessageManager,
    fake_bot: FakeBot,
) -> None:
    await client.send("/start")

    [policy] = [
        button
        for button in _buttons(message_manager.last_message())
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

    user = await _user(bot_session, client)
    stmt = select(events_table.c.payload).where(
        events_table.c.type == EventType.CONSENT_GIVEN,
        events_table.c.user_id == user.id,
    )
    assert (await bot_session.execute(stmt)).scalars().all() == [
        {"source": source.value, "version": CONSENT_VERSION},
    ]


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
    await _consented(client, message_manager)
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
    await _consented(client, message_manager)
    shows.clear()

    await _bot_started(client, "demo_staff_1")

    notice = DEMO_STAFF_NOTICE.format(org="Демо-УК «1»")
    assert notices.texts == [notice]
    assert _opened(notices.buttons[-1]) == [(CABINET_BUTTON, "/admin/requests")]
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

    user = await _user(bot_session, client)
    assert user.consent_at is not None
    assert user.consent_version == CONSENT_VERSION
    assert await _events_of(bot_session, user.id, EventType.CONSENT_GIVEN) == 1
    assert notices.texts == [NOT_SEEDED]
    assert MENU_TEXT in _text(message_manager)


@pytest.mark.parametrize(
    ("role", "joined"),
    [(OrgRole.EMPLOYEE, ORG_JOINED), (OrgRole.EXECUTOR, EXECUTOR_JOINED)],
)
async def test_the_org_name_is_escaped_in_the_invite_notice(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
    role: OrgRole,
    joined: str,
) -> None:
    user_id = await _started(bot_session, client)
    org_name = f"УК <{secrets.token_hex(4)}> & {secrets.token_hex(4)}"
    org_id = await _org(bot_session, name=org_name)
    code = secrets.token_hex(4)
    bot_session.add(
        OrgInvite(
            code=code,
            org_id=org_id,
            role=role,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            max_activations=1,
            created_by=user_id,
        ),
    )
    await bot_session.commit()
    await client.click(message_manager.last_message(), ACCEPT)

    await _bot_started(client, org_invite_payload(code))

    assert notices.texts == [joined.format(name=escape(org_name))]


FIND_HOUSE = InlineButtonTextLocator("🔎 Найти дом")
BY_ADDRESS = InlineButtonTextLocator("🗺 Выбрать адрес")
BACK_BUTTON = InlineButtonTextLocator("⬅️ Назад")
NAVIGATION = ["⬅️ Назад", "🏠 Меню"]


async def _search_by_address(
    client: BotClient,
    message_manager: MockMessageManager,
) -> None:
    await _consented(client, message_manager)
    await client.click(message_manager.last_message(), FIND_HOUSE)
    await client.click(message_manager.last_message(), BY_ADDRESS)


def _buttons(message: Message) -> list[Any]:
    keyboard = message.body.keyboard
    return [] if keyboard is None else [b for row in keyboard.buttons for b in row]


def _button_texts(message: Message) -> list[str]:
    return [str(button.text) for button in _buttons(message)]


def _spot() -> tuple[Decimal, Decimal]:
    return (
        Decimal(secrets.randbelow(60_000_000) + 10_000_000) / 1_000_000,
        Decimal(secrets.randbelow(170_000_000)) / 1_000_000,
    )


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
    await _consented(client, message_manager)
    await client.click(message_manager.last_message(), FIND_HOUSE)
    if by_geo:
        location = LocationAttachment(latitude=float(lat), longitude=float(lon))
        await _send(client, location)
    else:
        await client.click(message_manager.last_message(), BY_ADDRESS)
        await client.send(f"Назад{tag}")
        await client.send(f"Улица{tag}")
    await client.send("нет такого")

    await client.click(message_manager.last_message(), BACK_BUTTON)

    text = _text(message_manager)
    assert (METHOD_TEXT if by_geo else STREET_TEXT.format(city=f"Назад{tag}")) in text
    assert "Не нашлось" not in text


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
        "1",
        "2",
        "10",
        "⏭ Пропустить",
        *NAVIGATION,
    ]
    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert SEARCH_HOUSE_TEXT.format(street=f"Улица{tag}") in _text(message_manager)
    await client.send("1")
    await client.click(message_manager.last_message(), InlineButtonTextLocator("10"))

    user = await _user(bot_session, client)
    flat = await HousesRepo(bot_session).get_flat_by_number(house_id, "10")
    assert flat is not None
    stmt = select(residents_table.c.flat_id).where(
        residents_table.c.user_id == user.id,
        residents_table.c.house_id == house_id,
    )
    assert (await bot_session.execute(stmt)).scalars().all() == [flat.id]
    assert HOUSE_LINKED.format(address=address) in notices.texts


async def test_back_and_menu_walk_the_request_draft(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _consented(client, message_manager)
    _, house_id = await _org_house(bot_session)
    await _linked(bot_session, client, house_id, datetime.now(UTC))
    await client.click(message_manager.last_message(), NEW_REQUEST)

    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert "🛠 Что случилось?" in _text(message_manager)

    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
    await client.send("Течет кран на кухне")
    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert DESCRIPTION_TEXT in _text(message_manager)

    await client.send("Течет кран на кухне")
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert ATTACHMENTS_TEXT.format(attachments=0) in _text(message_manager)

    await client.click(message_manager.last_message(), TO_MENU)
    assert GREETING in _text(message_manager)
    await client.click(message_manager.last_message(), NEW_REQUEST)
    await client.click(message_manager.last_message(), TO_MENU)
    assert GREETING in _text(message_manager)


async def test_houses_near_a_location_are_listed_and_typing_filters_them_all(
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
    await _consented(client, message_manager)
    await client.click(message_manager.last_message(), FIND_HOUSE)
    [geo] = [
        button
        for button in _buttons(message_manager.last_message())
        if isinstance(button, RequestGeoLocationButton)
    ]
    assert geo.text == "📍 По геолокации"

    await _send(
        client,
        LocationAttachment(latitude=float(lat), longitude=float(lon)),
    )
    assert NEARBY_TEXT in _text(message_manager)
    assert sorted(_button_texts(message_manager.last_message())) == sorted(
        ["🏢 Сужения, 15", "🏢 Сужения, 51", "🏢 Сужения, 151", *NAVIGATION],
    )
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
    await _consented(client, message_manager)
    house_id, address = await _bot_house(
        bot_session,
        street=f"Разметки <&> {secrets.token_hex(3)}",
        org_id=await _org(bot_session),
    )
    await _linked(bot_session, client, house_id, datetime.now(UTC))
    description = "Давление <2 & <b>течет</b>"

    await client.click(message_manager.last_message(), NEW_REQUEST)
    assert CATEGORY_TEXT.format(address=escape(address)) in _text(message_manager)
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
    await client.send(description)
    await client.click(message_manager.last_message(), NEXT)

    assert f"\n\n{escape(description)}\n\n" in _text(message_manager)
    assert CONFIRM_TEXT.split("{", 1)[0] in _text(message_manager)


async def test_a_deeplinked_flat_step_goes_back_to_the_method_and_forgets_the_link(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    tag = secrets.token_hex(3)
    deeplinked, address = await _bot_house(bot_session)
    picked, _ = await _bot_house(
        bot_session,
        city=f"Забытый{tag}",
        street=f"Улица{tag}",
        building="1",
    )
    await _bot_started(client, entrance_qr_payload(deeplinked, 3))
    assert CONSENT_TEXT in _text(message_manager)
    await client.click(message_manager.last_message(), ACCEPT)
    assert _text(message_manager) == FLAT_NUMBER_TEXT.format(address=address)
    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert METHOD_TEXT in _text(message_manager)
    await client.click(message_manager.last_message(), BY_ADDRESS)
    await client.send(f"Забытый{tag}")
    await client.send(f"Улица{tag}")
    await client.send("1")
    await client.click(
        message_manager.last_message(),
        InlineButtonTextLocator("⏭ Пропустить"),
    )

    user = await _user(bot_session, client)
    stmt = select(events_table.c.payload).where(
        events_table.c.type == EventType.HOUSE_LINKED,
        events_table.c.user_id == user.id,
    )
    [payload] = (await bot_session.execute(stmt)).scalars().all()
    assert payload["house_id"] == picked
    assert payload["source"] == EventSource.DIRECT.value
    assert payload["entrance"] is None


CANCEL = InlineButtonTextLocator("❌ Отмена")


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

    assert GREETING in _text(message_manager)
    assert (await _status(bot_session, request_id)).status is RequestStatus.ON_REVIEW


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


@pytest.mark.parametrize("resend", [True, False])
async def test_a_repin_or_a_failed_edit_sends_the_list_anew_and_deletes_the_old(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
    resend: bool,
) -> None:
    chat_id, _ = await _listed_chat(bot_session, client, "Вода", pins_mid="list-7")
    pin_api.current = "list-7"
    pin_api.edit_fails = not resend

    await _run(
        task_broker,
        sync_chat_pins,
        chat_id=chat_id,
        notify=False,
        resend=resend,
    )

    assert pin_api.edited == []
    assert len(pin_api.sent) == 1
    assert pin_api.pinned == [
        {"chat_id": chat_id, "message_id": "list-1", "notify": False},
    ]
    assert pin_api.deleted == ["list-7"]
    assert await _pins_mid(bot_session, chat_id) == "list-1"


async def test_the_bot_sets_its_commands_and_a_failure_is_not_fatal(
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[list[BotCommand]] = []

    async def edit_my_commands(*, commands: list[BotCommand]) -> None:
        sent.append(commands)
        raise MaxBotNetworkError(message="timeout")

    monkeypatch.setattr(fake_bot, "edit_my_commands", edit_my_commands)

    await set_commands_handler(fake_bot)

    assert sent == [BOT_COMMANDS]


async def _org(session: AsyncSession, **fields: Any) -> OrgId:
    org = Organization(
        **{
            "timezone": "Europe/Moscow",
            "name": f"УК {secrets.token_hex(4)}",
            "inn": secrets.token_hex(6),
            "phone": "+70000000000",
            "address": "Тестовая область, Тестоград, Тестовая, 1",
            "registered_at": datetime.now(UTC),
            **fields,
        },
    )
    session.add(org)
    await session.flush()
    org_id = org.id
    await session.commit()
    return org_id


async def _consented(client: BotClient, message_manager: MockMessageManager) -> None:
    await client.send("/start")
    await client.click(message_manager.last_message(), ACCEPT)


async def _forbidden(**_: Any) -> Any:
    raise MaxBotForbiddenError(code="chat.denied", error="", message="")


def _join_house(bot: FakeBot, house_id: HouseId) -> list[list[LinkButton]]:
    url = create_start_link(bot, house_payload(house_id))
    return [[LinkButton(text=JOIN_HOUSE, url=url)]]


def _opened(buttons: list[Any]) -> list[tuple[str, str | None]]:
    return [
        (
            button.text,
            json.loads(decode_payload(button.payload))["path"]
            if isinstance(button.payload, str)
            else None,
        )
        for button in buttons
        if isinstance(button, OpenAppButton)
    ]


async def _resident_of_a_connected_house(
    session: AsyncSession,
    client: BotClient,
    message_manager: MockMessageManager,
) -> tuple[HouseId, str]:
    await _consented(client, message_manager)
    house_id, address = await _bot_house(session, org_id=await _org(session))
    await _linked(session, client, house_id, datetime.now(UTC))
    return house_id, address


async def test_the_menu_shows_the_house_and_the_cabinet_to_staff(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    house_id, address = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )

    await client.send("/start")

    assert _text(message_manager) == HOUSE_MENU_TEXT.format(address=address)
    assert _button_texts(message_manager.last_message()) == [
        "🚨 Авария",
        "📝 Подать заявку",
        DIGEST_BUTTON,
        "📱 Открыть приложение",
        "🔎 Другой дом",
    ]
    house = await HousesRepo(bot_session).get(house_id)
    assert house is not None
    assert house.org_id is not None
    user = await _user(bot_session, client)
    bot_session.add(
        OrgMember(org_id=house.org_id, user_id=user.id, role=OrgRole.EMPLOYEE),
    )
    await bot_session.commit()

    await client.send("/start")

    assert _text(message_manager) == (
        f"{HOUSE_MENU_TEXT.format(address=address)}\n\n{STAFF_TEXT}"
    )
    assert _opened(_buttons(message_manager.last_message())) == [
        ("📱 Открыть приложение", None),
        (CABINET_BUTTON, "/admin/requests"),
    ]


DIGEST = InlineButtonTextLocator(DIGEST_BUTTON)
SUBSCRIBE_DIGEST = InlineButtonTextLocator(DIGEST_SUBSCRIBE)


async def test_the_digest_window_takes_the_sunday_subscription(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    user_id = (await _user(bot_session, client)).id
    await client.send("/start")

    await client.click(message_manager.last_message(), DIGEST)

    assert _text(message_manager) == DIGEST_EMPTY
    await client.click(message_manager.last_message(), SUBSCRIBE_DIGEST)

    assert notices.texts == [DIGEST_SUBSCRIBED]
    bot_session.expire_all()
    levels = await NotificationsRepo(bot_session).get_levels(user_id)
    assert levels[NotificationCategory.DIGEST] is NotificationLevel.SILENT
    await client.click(message_manager.last_message(), DIGEST)
    assert SUBSCRIBE_DIGEST.find_button(message_manager.last_message()) is None


async def test_every_category_is_one_tap_away(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)

    await client.click(message_manager.last_message(), NEW_REQUEST)

    assert _button_texts(message_manager.last_message()) == [
        "🚨 Авария",
        *(CATEGORY_RULES[category].caption for category in RequestCategory),
        "🏠 Меню",
    ]


async def _send_photo(client: BotClient, caption: str | None) -> None:
    photo = PhotoAttachmentPayload(photo_id=1, token=PHOTO_TOKEN, url=RESULT_URL)
    message = Message(
        sender=client.user,
        recipient=Recipient(chat_type=ChatType.DIALOG, chat_id=client.chat.chat_id),
        timestamp=datetime.now(UTC),
        body=MessageBody(
            mid=secrets.token_hex(4),
            seq=1,
            text=caption,
            attachments=[PhotoAttachment(payload=photo)],
        ),
    )
    await _feed(client, MessageCreated(message=message, timestamp=datetime.now(UTC)))


async def test_a_photo_at_the_description_step_is_kept_and_its_caption_describes(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    await client.click(message_manager.last_message(), NEW_REQUEST)
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)

    await _send_photo(client, None)
    assert _text(message_manager) == (
        f"{DESCRIPTION_TEXT}\n\n{DESCRIPTION_ATTACHMENTS_TEXT.format(attachments=1)}"
    )
    await _send_photo(client, "Течет из-под ванны")

    assert _text(message_manager) == ATTACHMENTS_TEXT.format(attachments=2)
    await client.click(message_manager.last_message(), NEXT)
    assert "Течет из-под ванны" in _text(message_manager)


async def test_a_bot_request_is_confirmed_with_its_deadline_and_a_link_to_it(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    fake_bot: FakeBot,
) -> None:
    house_id, _ = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )
    await _draft_request(client, message_manager)
    assert SENT_TEXT in _text(message_manager)

    await _run(
        task_broker,
        create_bot_request,
        **bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1],
    )

    user = await _user(bot_session, client)
    stmt = select(Request).where(requests_table.c.author_user_id == user.id)
    request = (await bot_session.execute(stmt)).scalar_one()
    house = await HousesRepo(bot_session).get(house_id)
    assert house is not None
    assert request.react_deadline_at is not None
    react = house.local(request.react_deadline_at)
    deadline = house.local(request.deadline_at)
    assert _text(message_manager) == CREATED_TEXT.format(
        request_id=request.id,
        deadline=(
            f"⏱ Локализовать аварию до {react:%H:%M %d.%m}\n"
            f"⏰ Срок: до {deadline:%H:%M %d.%m}\n"
            "📜 ПП РФ № 416, п. 13: локализовать аварию - за 30 минут с регистрации "
            "заявки, устранить - не более 3 суток с даты аварии"
        ),
    )
    assert _opened(_buttons(message_manager.last_message())) == [
        (OPEN_REQUEST, f"/requests/{request.id}"),
    ]
    assert [
        button.web_app
        for button in _buttons(message_manager.last_message())
        if isinstance(button, OpenAppButton)
    ] == [fake_bot.state.info.username]


async def _create_for_a_stranger_house(
    task_broker: InMemoryBroker,
    session: AsyncSession,
    client: BotClient,
) -> Any:
    user_id = await _started(session, client)
    house_id, _ = await _bot_house(session, org_id=await _org(session))
    task: Any = create_bot_request
    sent = (
        await task.kicker()
        .with_broker(task_broker)
        .kiq(
            user_id=user_id,
            house_id=house_id,
            flat_id=None,
            category=RequestCategory.LEAK.value,
            description="Течет кран",
            photo_urls=[],
            channel=RequestChannel.BOT.value,
            stack_id=DEFAULT_STACK_ID,
        )
    )
    return await sent.wait_result(timeout=5)


async def test_a_refused_bot_request_says_why_and_leads_to_the_menu(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    result = await _create_for_a_stranger_house(task_broker, bot_session, client)

    assert not result.is_err
    assert _text(message_manager) == NOT_CREATED.format(reason=HOUSE_NOT_FOUND)
    assert _button_texts(message_manager.last_message()) == ["🏠 Меню"]


async def test_an_unexpected_failure_of_a_bot_request_still_answers(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken(*_: Any, **__: Any) -> None:
        raise RuntimeError(PROBE_DENIED)

    monkeypatch.setattr(RequestsService, "create", broken)

    result = await _create_for_a_stranger_house(task_broker, bot_session, client)

    assert result.is_err
    assert _text(message_manager) == NOT_CREATED_UNEXPECTED


async def test_an_unexpected_error_is_answered_and_the_menu_restarts(
    client: BotClient,
    message_manager: MockMessageManager,
    notices: _RecordingBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await client.send("/start")

    async def broken(*_: Any, **__: Any) -> None:
        raise RuntimeError(PROBE_DENIED)

    monkeypatch.setattr(EventsService, "record", broken)
    message_manager.reset_history()

    await client.send("/start")

    assert notices.texts == [UNEXPECTED]
    await _rendered(message_manager, MENU_TEXT)


async def test_the_registration_link_opens_its_page_in_the_mini_app(
    client: BotClient,
    message_manager: MockMessageManager,
    notices: _RecordingBot,
) -> None:
    await _consented(client, message_manager)

    await _bot_started(client, "reg_secret-code")

    assert notices.texts == [REGISTER_NOTICE]
    assert _opened(notices.buttons[-1]) == [
        (REGISTER_BUTTON, "/register/secret-code"),
    ]


async def test_a_request_notification_carries_the_button_to_the_request(
    client: BotClient,
    task_broker: InMemoryBroker,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    user_id = await _started(bot_session, client)

    await _run(
        task_broker,
        send_to_user,
        user_id=user_id,
        text="🔔 Проба",
        category=NotificationCategory.REQUESTS.value,
        mandatory=True,
        app_button=OPEN_REQUEST,
        app_path="/requests/1",
    )

    assert notices.texts == ["🔔 Проба"]
    assert _opened(notices.buttons[-1]) == [(OPEN_REQUEST, "/requests/1")]


UNEXPECTED_PROBE_COMMAND = "unexpectedprobe"


@error_probe_router.message_created(Command(UNEXPECTED_PROBE_COMMAND))
async def unexpected_probe_handler(_update: MessageCreated) -> None:
    raise RuntimeError(PROBE_DENIED)


async def test_an_unexpected_error_in_a_house_chat_opens_no_menu_there(
    client: BotClient,
    bot_setup: BotSetup,
    message_manager: MockMessageManager,
) -> None:
    await _consented(client, message_manager)
    recorder = _RecordingBot()
    outside = _in_chat(bot_setup, recorder, _chat_id(), client.user.id)
    message_manager.reset_history()

    await outside.send(f"/{UNEXPECTED_PROBE_COMMAND}")
    await asyncio.sleep(0.1)

    assert recorder.texts == [UNEXPECTED]
    assert message_manager.sent_messages == []


async def test_a_menu_that_fails_to_render_is_not_restarted_in_a_loop(
    client: BotClient,
    message_manager: MockMessageManager,
    notices: _RecordingBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _consented(client, message_manager)
    calls: list[UserId] = []

    async def broken(_: ProfileService, user_id: UserId) -> None:
        calls.append(user_id)
        raise RuntimeError(PROBE_DENIED)

    monkeypatch.setattr(ProfileService, "me", broken)

    await client.send("/start")
    await asyncio.sleep(0.2)

    assert notices.texts == [UNEXPECTED]
    assert len(calls) == 2


async def test_a_user_without_a_max_account_gets_nothing_but_a_group_does() -> None:
    recorder = _RecordingBot()
    sender = MaxSender(recorder, cast(BgManagerFactory, _NotifyProbe()))

    assert await sender.send_message("Заявка", user_id=MaxUserId(-5)) is None
    await sender.send_message("Объявление", chat_id=MaxChatId(-70))

    assert recorder.texts == ["Объявление"]


PROBLEM = "В третьем подъезде не горит свет на 5 этаже"


async def test_a_free_text_quotes_the_problem_and_skips_the_description(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    _, address = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )

    await client.send(PROBLEM)

    assert _text(message_manager) == PROBLEM_TEXT.format(
        address=address,
        description=PROBLEM,
    )
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
    assert _text(message_manager) == ATTACHMENTS_TEXT.format(attachments=0)
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)
    enqueued = bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1]
    assert enqueued["description"] == PROBLEM


async def test_a_photo_with_a_caption_starts_a_request_with_the_photo(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    _, address = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )

    await _send_photo(client, PROBLEM)

    assert _text(message_manager) == PROBLEM_TEXT.format(
        address=address,
        description=PROBLEM,
    )
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
    assert _text(message_manager) == ATTACHMENTS_TEXT.format(attachments=1)


async def test_a_long_problem_is_quoted_short_and_escaped_but_sent_whole(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    _, address = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )
    problem = f"Течет <вода> & {'капает ' * 40}".strip()

    await client.send(problem)

    assert _text(message_manager) == PROBLEM_TEXT.format(
        address=address,
        description=f"{escape(problem[:200])}…",
    )
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)
    enqueued = bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1]
    assert enqueued["description"] == problem


@pytest.mark.parametrize("text", ["Спасибо", "/помогите, течет кран на кухне"])
async def test_a_short_text_or_a_command_opens_the_menu(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    text: str,
) -> None:
    _, address = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )

    await client.send(text)

    assert _text(message_manager) == HOUSE_MENU_TEXT.format(address=address)


async def test_a_free_text_without_consent_asks_for_it(
    client: BotClient,
    message_manager: MockMessageManager,
) -> None:
    await client.send(PROBLEM)

    assert CONSENT_TEXT in _text(message_manager)


async def test_a_free_text_without_a_house_sends_to_the_house_search(
    client: BotClient,
    message_manager: MockMessageManager,
) -> None:
    await _consented(client, message_manager)

    await client.send(PROBLEM)

    assert _text(message_manager) == NO_HOUSE_TEXT


async def test_a_free_text_with_no_window_open_starts_a_request(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    users = UsersRepo(bot_session)
    user = await users.upsert_by_max_id(MaxUserId(client.user.id), "Житель", None)
    await users.set_consent(user.id, CONSENT_VERSION)
    await bot_session.commit()
    house_id, address = await _bot_house(bot_session, org_id=await _org(bot_session))
    await _linked(bot_session, client, house_id, datetime.now(UTC))

    await client.send(PROBLEM)

    assert _text(message_manager) == PROBLEM_TEXT.format(
        address=address,
        description=PROBLEM,
    )


@pytest.mark.parametrize(
    ("text", "drafted"),
    [(" Течет кран тут ", False), (" Течет кран дома ", True)],
)
def test_a_draft_takes_a_free_text_of_fifteen_characters(
    text: str,
    drafted: bool,
) -> None:
    body = MessageBody(mid="1", seq=1, text=text)

    assert (NewRequestData.from_free_text(body) is not None) is drafted


async def test_a_free_text_on_the_category_step_quotes_the_problem(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    _, address = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )
    await client.click(message_manager.last_message(), NEW_REQUEST)
    assert _text(message_manager) == CATEGORY_TEXT.format(address=address)

    await client.send(PROBLEM)

    assert _text(message_manager) == PROBLEM_TEXT.format(
        address=address,
        description=PROBLEM,
    )


async def test_a_free_text_after_a_sent_request_starts_a_new_one(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    _, address = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )
    await client.send(PROBLEM)
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)
    assert SENT_TEXT in _text(message_manager)
    problem = "Во дворе третий день не вывозят мусор"

    await client.send(problem)

    assert _text(message_manager) == PROBLEM_TEXT.format(
        address=address,
        description=problem,
    )


async def test_a_free_text_in_the_menu_without_consent_asks_for_it(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    user = await _user(bot_session, client)
    user.consent_at = None
    await bot_session.commit()

    await client.send(PROBLEM)

    assert CONSENT_TEXT in _text(message_manager)


async def test_a_chat_broadcast_carries_the_link_into_the_app(
    task_broker: InMemoryBroker,
    fake_bot: FakeBot,
    notices: _RecordingBot,
) -> None:
    chat_id = _chat_id()

    await _run(
        task_broker,
        broadcast_to_chats,
        chat_ids=[chat_id],
        text="🗳 Опрос",
        app_button=VOTE,
        app_path="/meetings/7",
    )

    url = create_startapp_link(fake_bot, app_payload("/meetings/7"))
    assert notices.buttons == [[LinkButton(text=VOTE, url=url)]]


async def _demo_flat(
    session: AsyncSession,
    client: BotClient,
) -> tuple[UserId, HouseId, FlatId]:
    user_id = (await _user(session, client)).id
    residents = select(residents_table.c.flat_id).where(
        residents_table.c.user_id == user_id,
    )
    flat_id = (await session.execute(residents)).scalar_one()
    flat = await HousesRepo(session).get_flat(flat_id)
    assert flat is not None
    assert flat.number == demo_flat_number(user_id)
    return user_id, flat.house_id, flat_id


@pytest.mark.parametrize("status", [RequestStatus.NEW, RequestStatus.ACCEPTED])
async def test_a_demo_executor_link_hands_the_own_demo_request_to_the_caller(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    shows: list[Show],
    notices: _RecordingBot,
    status: RequestStatus,
) -> None:
    org_id, _address = await _bot_demo(bot_session)
    await _consented(client, message_manager)
    await _bot_started(client, "demo_resident_1")
    await _bot_started(client, "demo_staff_1")
    user_id, house_id, flat_id = await _demo_flat(bot_session, client)
    older = await _request(
        bot_session,
        house_id,
        status,
        author=user_id,
        flat=flat_id,
    )
    request_id = await _request(
        bot_session,
        house_id,
        status,
        author=user_id,
        flat=flat_id,
    )
    unrelated = await _request(bot_session, house_id, status)

    await _bot_started(client, "demo_executor_1")

    assert DEMO_EXECUTOR_NOTICE.format(org="Демо-УК «1»") in notices.texts
    roles, _houses = await _demo_roles(bot_session, client)
    assert roles == [(org_id, OrgRole.EXECUTOR)]
    request = await _status(bot_session, request_id)
    assert request.status is RequestStatus.ACCEPTED
    assert request.executor_user_id == user_id
    assert (await _status(bot_session, older)).executor_user_id is None
    assert (await _status(bot_session, unrelated)).executor_user_id is None
    enqueued = bot_broker.enqueued(TaskName.SEND_EXECUTOR_CARD)[-1]
    assert enqueued == {"request_id": request_id, "user_id": None}

    await _run(task_broker, send_executor_card, **enqueued)
    await client.click(message_manager.last_message(), DEPART)

    assert any(f"№{request_id}:" in (text or "") for _, text, *_ in shows)
    assert (await _status(bot_session, request_id)).status is (
        RequestStatus.IN_PROGRESS
    )


async def test_a_demo_executor_link_without_an_open_demo_request_asks_for_one(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    notices: _RecordingBot,
) -> None:
    await _bot_demo(bot_session, 2)
    await _consented(client, message_manager)
    await _bot_started(client, "demo_resident_2")
    user_id, house_id, flat_id = await _demo_flat(bot_session, client)
    done = await _request(
        bot_session,
        house_id,
        RequestStatus.IN_PROGRESS,
        author=user_id,
        flat=flat_id,
    )
    cards = len(bot_broker.enqueued(TaskName.SEND_EXECUTOR_CARD))

    await _bot_started(client, "demo_executor_2")

    assert notices.texts[-1] == NO_DEMO_REQUEST.format(number=2)
    assert (await _status(bot_session, done)).executor_user_id is None
    assert len(bot_broker.enqueued(TaskName.SEND_EXECUTOR_CARD)) == cards


async def test_the_checkers_demo_org_refuses_a_demo_executor_link(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    await _bot_demo(bot_session, 5)
    await _consented(client, message_manager)

    await _bot_started(client, "demo_executor_5")

    assert notices.texts == [CHECKER_RESERVED]
    assert await _demo_roles(bot_session, client) == ([], [])


@pytest.mark.parametrize("with_flat", [True, False])
async def test_the_demo_command_sends_every_reminder_to_the_caller_only(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    notices: _RecordingBot,
    with_flat: bool,
) -> None:
    _org_id, address = await _bot_demo(bot_session, 3)
    await _consented(client, message_manager)
    serial, place = DEMO_SERIAL, DEMO_ADDRESS
    if with_flat:
        await _bot_started(client, "demo_resident_3")
        _user_id, _house_id, flat_id = await _demo_flat(bot_session, client)
        serial, place = f"ДЕМО-ГВ-{flat_id:06d}", address
    user_id = (await _user(bot_session, client)).id
    notices.texts.clear()
    queued = len(bot_broker.enqueued(TaskName.SEND_TO_USER))

    await client.send("/demo")

    assert notices.texts == [DEMO_REMINDERS_TEXT]
    sent = bot_broker.enqueued(TaskName.SEND_TO_USER)[queued:]
    assert [message["text"].split()[0] for message in sent] == [
        "📟",
        "⏰",
        "📟",
        "⏰",
        "⏰",
        "⚠️",
        "🗳",
        "📅",
    ]
    assert {message["user_id"] for message in sent} == {user_id}
    assert all(message["mandatory"] for message in sent)
    assert all(message["app_button"] for message in sent)
    assert all(serial in message["text"] for message in sent[3:6])
    assert place in sent[-1]["text"]


async def test_a_demo_executor_link_without_a_demo_flat_asks_for_a_request(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    await _bot_demo(bot_session, 2)
    await _consented(client, message_manager)

    await _bot_started(client, "demo_executor_2")

    assert notices.texts[-1] == NO_DEMO_REQUEST.format(number=2)


async def test_a_demo_executor_link_without_a_request_keeps_the_staff_role(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    org_id, _address = await _bot_demo(bot_session, 2)
    await _consented(client, message_manager)
    await _bot_started(client, "demo_staff_2")

    await _bot_started(client, "demo_executor_2")

    assert notices.texts[-1] == NO_DEMO_REQUEST.format(number=2)
    roles, _houses = await _demo_roles(bot_session, client)
    assert roles == [(org_id, OrgRole.EMPLOYEE)]


EMERGENCY = InlineButtonTextLocator("🚨 Авария")


def _copied(message: Message) -> list[tuple[str, str]]:
    return [
        (button.text, button.payload)
        for button in _buttons(message)
        if isinstance(button, ClipboardButton)
    ]


async def test_the_emergency_screen_gives_the_house_emergency_line_to_copy(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _consented(client, message_manager)
    phone = "+7 (000) 111-22-33"
    house_id, _ = await _bot_house(
        bot_session,
        org_id=await _org(bot_session, emergency_phone=phone),
    )
    await _linked(bot_session, client, house_id, datetime.now(UTC))
    await client.send("/start")

    await client.click(message_manager.last_message(), EMERGENCY)

    assert _text(message_manager) == "\n\n".join(
        [
            EMERGENCY_TEXT,
            EMERGENCY_PHONE_TEXT.format(emergency_phone=phone),
            CALL_NOTE_TEXT,
        ],
    )
    assert _copied(message_manager.last_message()) == [
        ("📋 Номер аварийной службы", phone),
    ]
    await client.click(message_manager.last_message(), NEW_REQUEST)
    assert FIRST_CATEGORY.find_button(message_manager.last_message()) is not None


async def test_the_emergency_screen_labels_the_org_phone_of_a_registry_house(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _consented(client, message_manager)
    org_id = await _org(bot_session, registered_at=None, phone="+7 (000) 555-00-00")
    house_id, address = await _bot_house(bot_session, org_id=org_id)
    await _linked(bot_session, client, house_id, datetime.now(UTC))
    await client.click(message_manager.last_message(), NEW_REQUEST)
    assert NOT_CONNECTED_TEXT.format(address=address) in _text(message_manager)

    await client.click(message_manager.last_message(), EMERGENCY)

    assert _text(message_manager) == "\n\n".join(
        [
            EMERGENCY_TEXT,
            NO_EMERGENCY_PHONE_TEXT,
            ORG_PHONE_TEXT.format(org_phone="+7 (000) 555-00-00"),
            CALL_NOTE_TEXT,
        ],
    )
    assert _button_texts(message_manager.last_message()) == [
        "📋 Телефон УК",
        "🏠 Меню",
    ]


async def test_the_emergency_screen_works_without_a_house(
    client: BotClient,
    message_manager: MockMessageManager,
) -> None:
    await _consented(client, message_manager)

    await client.click(message_manager.last_message(), EMERGENCY)

    assert _text(message_manager) == (
        f"{EMERGENCY_TEXT}\n\n{NO_EMERGENCY_PHONE_TEXT}\n\n{CALL_NOTE_TEXT}"
    )
    assert _button_texts(message_manager.last_message()) == ["🏠 Меню"]


async def test_a_free_text_on_the_emergency_screen_starts_a_request(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    _, address = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )
    await client.send("/start")
    await client.click(message_manager.last_message(), EMERGENCY)

    await client.send(PROBLEM)

    assert _text(message_manager) == PROBLEM_TEXT.format(
        address=address,
        description=PROBLEM,
    )


DECLINE = InlineButtonTextLocator("🙅 Не могу")


async def test_a_declining_executor_is_asked_why_and_loses_the_card(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    shows: list[Show],
    notices: _RecordingBot,
) -> None:
    request_id = await _executor_on(bot_session, client, RequestStatus.ACCEPTED)
    executor = (await _status(bot_session, request_id)).executor_user_id
    await _run(task_broker, send_executor_card, request_id=request_id)
    await client.click(message_manager.last_message(), DECLINE)
    await _rendered(message_manager, DECLINE_TEXT)
    assert _shown(shows, DECLINE_TEXT)[0] is ShowMode.SEND

    await client.send("Уехал на другой вызов")

    request = await _status(bot_session, request_id)
    assert request.executor_user_id is None
    assert request.status is RequestStatus.ACCEPTED
    assert DECLINE_SENT in notices.texts
    assert MENU_TEXT in _text(message_manager)
    enqueued = bot_broker.enqueued(TaskName.SEND_EXECUTOR_CARD)[-1]
    assert enqueued == {"request_id": request_id, "user_id": executor}
    await _run(task_broker, send_executor_card, **enqueued)
    _, text, chat_id, _ = shows[-1]
    assert NOT_YOURS_TEXT.format(request_id=request_id) in (text or "")
    assert chat_id == client.chat.chat_id


async def _announcement(
    session: AsyncSession,
    house_id: HouseId,
    created_by: UserId,
) -> AnnouncementId:
    house = await HousesRepo(session).get(house_id)
    assert house is not None
    assert house.org_id is not None
    announcement = Announcement(
        org_id=house.org_id,
        house_ids=[house_id],
        text="Отключат воду",
        channels=["direct", "chat"],
        created_by=created_by,
        recipients_count=2,
    )
    session.add(announcement)
    await session.flush()
    announcement_id = announcement.id
    await session.commit()
    return announcement_id


async def _delivered(
    session: AsyncSession,
    announcement_id: AnnouncementId,
) -> tuple[int | None, int | None]:
    stmt = select(
        announcements_table.c.delivered_direct,
        announcements_table.c.delivered_chat,
    ).where(announcements_table.c.id == announcement_id)
    result = await session.execute(stmt)
    direct, chat = result.one()
    return direct, chat


@pytest.mark.usefixtures("refusing_chats")
async def test_a_chat_that_refused_the_announcement_counts_as_undelivered(
    client: BotClient,
    task_broker: InMemoryBroker,
    chat_api: _ChatApi,
    bot_session: AsyncSession,
) -> None:
    chat_api.is_admin = False
    chat_id = await _bound_chat(bot_session, client)
    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None
    assert chat.house_id is not None
    user = await _user(bot_session, client)
    announcement_id = await _announcement(bot_session, chat.house_id, user.id)

    await _run(
        task_broker,
        broadcast_to_chats,
        chat_ids=[chat_id],
        text="Отключат воду",
        announcement_id=announcement_id,
    )

    assert await _delivered(bot_session, announcement_id) == (None, 0)


async def test_a_resident_who_stopped_the_bot_is_not_counted_as_delivered(
    client: BotClient,
    task_broker: InMemoryBroker,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    house_id = await _staff(bot_session, client)
    user_id = (await _user(bot_session, client)).id
    stopped = User(
        max_user_id=_max_id(),
        max_chat_id=MaxChatId(secrets.randbits(40)),
        name="Сосед",
        bot_stopped_at=datetime.now(UTC),
    )
    bot_session.add(stopped)
    await bot_session.flush()
    stopped_id = stopped.id
    announcement_id = await _announcement(bot_session, house_id, user_id)

    await _run(
        task_broker,
        broadcast_to_users,
        user_ids=[user_id, stopped_id],
        text="Отключат воду",
        category=NotificationCategory.ANNOUNCEMENTS.value,
        mandatory=False,
        announcement_id=announcement_id,
    )

    assert notices.texts == ["Отключат воду"]
    assert await _delivered(bot_session, announcement_id) == (1, None)


async def test_delete_forgets_the_user_and_the_next_start_asks_for_consent(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    await _consented(client, message_manager)
    user_id = (await _user(bot_session, client)).id

    await client.send("/delete")
    await client.click(
        message_manager.last_message(),
        InlineButtonTextLocator("🗑 Удалить"),
    )

    assert notices.texts == [FORGOTTEN_TEXT]
    bot_session.expire_all()
    forgotten = await UsersRepo(bot_session).get_by_id(user_id)
    assert forgotten is not None
    assert forgotten.name == FORGOTTEN_NAME
    await client.send("/start")
    assert _text(message_manager).startswith(CONSENT_TEXT)
    assert (await _user(bot_session, client)).id != user_id


async def test_delete_cancel_returns_to_the_entry_screen(
    client: BotClient,
    message_manager: MockMessageManager,
) -> None:
    await client.send("/delete")
    await client.click(
        message_manager.last_message(),
        InlineButtonTextLocator("↩️ Отмена"),
    )

    assert CONSENT_TEXT in _text(message_manager)

    await client.click(message_manager.last_message(), ACCEPT)
    await client.send("/delete")
    await client.click(
        message_manager.last_message(),
        InlineButtonTextLocator("↩️ Отмена"),
    )

    assert GREETING in _text(message_manager)


VOICE = "Лифт стоит на седьмом этаже и не едет"


def _voice(transcription: str | None = None) -> AudioAttachment:
    return AudioAttachment.factory(
        url="https://max.test/voice.ogg",
        token=secrets.token_hex(4),
        transcription=Omitted() if transcription is None else transcription,
    )


async def _on_description(
    session: AsyncSession,
    client: BotClient,
    message_manager: MockMessageManager,
) -> None:
    await _resident_of_a_connected_house(session, client, message_manager)
    await client.send("/start")
    await client.click(message_manager.last_message(), NEW_REQUEST)
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
    assert DESCRIPTION_TEXT in _text(message_manager)


async def test_a_transcribed_voice_describes_the_request(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    await _on_description(bot_session, client, message_manager)

    await _send(client, _voice(VOICE))

    assert _text(message_manager) == ATTACHMENTS_TEXT.format(attachments=0)
    await client.click(message_manager.last_message(), NEXT)
    assert VOICE in _text(message_manager)
    await client.click(message_manager.last_message(), SEND)
    assert bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1]["description"] == VOICE


async def test_a_voice_without_a_transcript_waits_for_it(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    await _on_description(bot_session, client, message_manager)

    await _send(client, _voice())

    assert VOICE_PENDING in _text(message_manager)
    queued = bot_broker.enqueued(TaskName.TRANSCRIBE_VOICE)[-1]
    assert queued["in_draft"] is True
    assert queued["draft"]["category"] == next(iter(RequestCategory)).value
    assert queued["user_id"] == (await _user(bot_session, client)).id


@pytest.fixture
def instant_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot_requests, "VOICE_RECHECK_SECONDS", 0)


def _reread(
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
    transcriptions: list[str | None],
) -> list[str]:
    asked: list[str] = []

    async def get_message_by_id(*, message_id: str) -> Message:
        asked.append(message_id)
        return Message(
            recipient=Recipient(chat_type=ChatType.DIALOG, chat_id=1),
            timestamp=datetime.now(UTC),
            body=MessageBody(
                mid=message_id,
                seq=1,
                text=None,
                attachments=[_voice(transcriptions.pop(0))],
            ),
        )

    monkeypatch.setattr(fake_bot, "get_message_by_id", get_message_by_id)
    return asked


@pytest.mark.usefixtures("instant_retries")
@pytest.mark.parametrize("in_draft", [True, False])
async def test_a_late_transcript_opens_the_next_step(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
    bot_session: AsyncSession,
    in_draft: bool,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    asked = _reread(fake_bot, monkeypatch, [VOICE])
    category = next(iter(RequestCategory))
    draft = NewRequestData(category=category if in_draft else None)

    await _run(
        task_broker,
        transcribe_voice,
        user_id=(await _user(bot_session, client)).id,
        mid="voice-1",
        draft=draft.to_data(),
        in_draft=in_draft,
    )

    assert asked == ["voice-1"]
    if in_draft:
        assert _text(message_manager) == ATTACHMENTS_TEXT.format(attachments=0)
    else:
        assert f"«{VOICE}»" in _text(message_manager)


@pytest.mark.usefixtures("instant_retries")
async def test_a_voice_never_transcribed_asks_for_text(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
    bot_session: AsyncSession,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    _reread(fake_bot, monkeypatch, [None])

    await _run(
        task_broker,
        transcribe_voice,
        user_id=(await _user(bot_session, client)).id,
        mid="voice-1",
        draft=NewRequestData(category=next(iter(RequestCategory))).to_data(),
        in_draft=True,
    )

    text = _text(message_manager)
    assert text.startswith(VOICE_FAILED)
    assert DESCRIPTION_TEXT in text
    await client.send(VOICE)
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)
    assert _text(message_manager) == SENT_TEXT


async def test_a_voice_in_the_menu_starts_a_request_or_waits_for_the_transcript(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    notices: _RecordingBot,
) -> None:
    _, address = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )
    await client.send("/start")

    await _send(client, _voice(VOICE))
    assert _text(message_manager) == PROBLEM_TEXT.format(
        address=address,
        description=VOICE,
    )
    await client.send("/start")
    await _send(client, _voice())

    assert notices.texts[-1] == VOICE_PENDING
    assert bot_broker.enqueued(TaskName.TRANSCRIBE_VOICE)[-1]["in_draft"] is False


async def _meter_owner(
    session: AsyncSession,
    client: BotClient,
    message_manager: MockMessageManager,
    *,
    last: int | None = None,
) -> MeterId:
    await _consented(client, message_manager)
    user_id = (await _user(session, client)).id
    _, house_id = await _org_house(session)
    flat = Flat(house_id=house_id, number="9")
    session.add(flat)
    await session.flush()
    session.add(
        Resident(
            user_id=user_id,
            house_id=house_id,
            flat_id=flat.id,
            role=ResidentRole.OWNER,
            verified_at=datetime.now(UTC),
        ),
    )
    meter = await MetersRepo(session).add(
        flat.id,
        MeterType.COLD_WATER,
        1,
        "SN-9",
        None,
    )
    assert meter is not None
    if last is not None:
        await MetersRepo(session).add_reading(
            meter.id,
            date(2020, 1, 1),
            {TariffZone.SINGLE: last},
            [],
            ocr_used=False,
            ocr_accepted=False,
            is_below_previous=False,
            submitted_at=datetime.now(UTC),
            submitted_by=user_id,
        )
    meter_id = meter.id
    await session.commit()
    return meter_id


async def test_a_meter_photo_in_the_menu_waits_for_recognition(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    meter_id = await _meter_owner(bot_session, client, message_manager)
    await client.send("/start")

    await _send_photo(client, None)

    assert _text(message_manager) == METER_WAIT_TEXT
    queued = bot_broker.enqueued(TaskName.RECOGNIZE_METER_PHOTO)[-1]
    assert queued["data"]["meter_id"] == meter_id
    assert queued["data"]["photo_url"] == RESULT_URL


async def test_a_meter_photo_without_a_verified_flat_is_refused(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    await client.send("/start")

    await _send_photo(client, None)

    assert NOT_VERIFIED in notices.texts


@pytest.fixture
def recognized(monkeypatch: pytest.MonkeyPatch) -> list[int | None]:
    values: list[int | None] = [12_345]

    async def save(*_: Any) -> list[str]:
        return [photo_name()]

    async def recognize(_self: Any, _name: str) -> dict[TariffZone, int] | None:
        value = values[0]
        return None if value is None else {TariffZone.SINGLE: value}

    monkeypatch.setattr(meter_tasks, "save_photos", save)
    monkeypatch.setattr(VisionClient, "recognize", recognize)
    monkeypatch.setattr(VisionClient, "configured", property(lambda _self: True))
    return values


async def _recognized_card(
    session: AsyncSession,
    client: BotClient,
    task_broker: InMemoryBroker,
    meter_id: MeterId,
) -> None:
    choice_period = datetime.now(ZoneInfo("Europe/Moscow")).date().replace(day=1)
    await _run(
        task_broker,
        recognize_meter_photo,
        user_id=(await _user(session, client)).id,
        data=MeterPhotoData(
            period=choice_period.isoformat(),
            meter_id=meter_id,
            photo_url=RESULT_URL,
        ).to_data(),
    )


@pytest.mark.usefixtures("recognized")
async def test_a_recognized_reading_is_confirmed_and_submitted(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    meter_id = await _meter_owner(bot_session, client, message_manager)

    await _recognized_card(bot_session, client, task_broker, meter_id)

    assert "12,345 м³" in _text(message_manager)
    await client.click(message_manager.last_message(), SEND_READING)
    assert any(
        (text or "").startswith("✅ Показание передано") for text in notices.texts
    )
    bot_session.expire_all()
    [reading] = await MetersRepo(bot_session).list_readings(meter_id, 5)
    assert reading.values == {"single": 12_345}
    assert (reading.ocr_used, reading.ocr_accepted) == (True, True)


async def test_an_unreadable_photo_takes_a_typed_reading(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    recognized: list[int | None],
) -> None:
    recognized[0] = None
    meter_id = await _meter_owner(bot_session, client, message_manager)

    await _recognized_card(bot_session, client, task_broker, meter_id)
    assert METER_UNREADABLE_TEXT in _text(message_manager)
    assert METER_MANUAL_TEXT not in _text(message_manager)
    await client.click(message_manager.last_message(), EDIT_READING)
    await client.send("123,4")

    assert "123,400 м³" in _text(message_manager)


@pytest.mark.usefixtures("recognized")
async def test_a_reading_below_the_last_one_needs_a_second_tap(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    meter_id = await _meter_owner(bot_session, client, message_manager, last=50_000)

    await _recognized_card(bot_session, client, task_broker, meter_id)
    await client.click(message_manager.last_message(), SEND_READING)

    assert ANOMALY_TEXT["below"] in _text(message_manager)
    bot_session.expire_all()
    assert len(await MetersRepo(bot_session).list_readings(meter_id, 5)) == 1
    await client.click(message_manager.last_message(), SEND_ANYWAY)
    bot_session.expire_all()
    assert len(await MetersRepo(bot_session).list_readings(meter_id, 5)) == 2


ACCEPT_CHAIR = InlineButtonTextLocator("✅ Принять")
DECLINE_CHAIR = InlineButtonTextLocator("❌ Отказаться")


async def _chairman_offer(
    session: AsyncSession,
    client: BotClient,
    message_manager: MockMessageManager,
) -> tuple[HouseId, UserId, str]:
    user_id = await _started(session, client)
    _, house_id = await _org_house(session)
    issuer = User(max_user_id=_max_id(), name="Пётр Председателев")
    session.add(issuer)
    await session.flush()
    session.add_all(
        [
            Resident(
                user_id=issuer.id,
                house_id=house_id,
                role=ResidentRole.OWNER,
                verified_at=datetime.now(UTC),
                is_chairman=True,
            ),
            Resident(
                user_id=user_id,
                house_id=house_id,
                role=ResidentRole.OWNER,
                verified_at=datetime.now(UTC),
            ),
        ],
    )
    code = secrets.token_hex(4)
    session.add(
        ChairmanHandover(
            code=code,
            house_id=house_id,
            created_by=issuer.id,
            expires_at=datetime.now(UTC) + timedelta(hours=48),
        ),
    )
    await session.commit()
    await client.click(message_manager.last_message(), ACCEPT)
    return house_id, user_id, code


async def test_a_chairman_deeplink_offers_the_role_and_hands_it_over(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    house_id, user_id, code = await _chairman_offer(
        bot_session,
        client,
        message_manager,
    )

    await _bot_started(client, chairman_payload(code))
    assert "предлагает вам стать председателем" in _text(message_manager)

    await client.click(message_manager.last_message(), ACCEPT_CHAIR)

    bot_session.expire_all()
    chairman = await ResidentsRepo(bot_session).get_chairman(house_id)
    assert chairman is not None
    assert chairman.user_id == user_id
    assert any("Вы председатель совета дома" in (text or "") for text in notices.texts)


async def test_a_declined_chairman_offer_leaves_the_role_with_the_issuer(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    house_id, user_id, code = await _chairman_offer(
        bot_session,
        client,
        message_manager,
    )

    await _bot_started(client, chairman_payload(code))
    await client.click(message_manager.last_message(), DECLINE_CHAIR)

    bot_session.expire_all()
    chairman = await ResidentsRepo(bot_session).get_chairman(house_id)
    assert chairman is not None
    assert chairman.user_id != user_id
    assert any("Вы отказались" in (text or "") for text in notices.texts)


async def test_a_chairman_link_opened_by_a_stranger_says_why(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    await _chairman_offer(bot_session, client, message_manager)
    _, other_house_id = await _org_house(bot_session)
    code = secrets.token_hex(4)
    issuer = User(max_user_id=_max_id(), name="Чужой Председатель")
    bot_session.add(issuer)
    await bot_session.flush()
    bot_session.add_all(
        [
            Resident(
                user_id=issuer.id,
                house_id=other_house_id,
                role=ResidentRole.OWNER,
                verified_at=datetime.now(UTC),
                is_chairman=True,
            ),
            ChairmanHandover(
                code=code,
                house_id=other_house_id,
                created_by=issuer.id,
                expires_at=datetime.now(UTC) + timedelta(hours=48),
            ),
        ],
    )
    await bot_session.commit()

    await _bot_started(client, chairman_payload(code))

    assert NOT_A_NEIGHBOUR in notices.texts


async def test_chairman_outcomes_escape_the_name_and_the_address(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    house_id, _, code = await _chairman_offer(bot_session, client, message_manager)
    handover = await ChairmanRepo(bot_session).get(code)
    assert handover is not None
    issuer_id = handover.created_by
    await bot_session.execute(
        update(User).where(users_table.c.id == issuer_id).values(name="Ян <Б>"),
    )
    await bot_session.execute(
        update(House).where(houses_table.c.id == house_id).values(street="Р&Д"),
    )
    await bot_session.commit()

    await _bot_started(client, chairman_payload(code))
    await client.click(message_manager.last_message(), DECLINE_CHAIR)

    assert any("Ян &lt;Б&gt; об этом узнает" in (text or "") for text in notices.texts)

    second = secrets.token_hex(4)
    bot_session.add(
        ChairmanHandover(
            code=second,
            house_id=house_id,
            created_by=issuer_id,
            expires_at=datetime.now(UTC) + timedelta(hours=48),
        ),
    )
    await bot_session.commit()

    await _bot_started(client, chairman_payload(second))
    await client.click(message_manager.last_message(), ACCEPT_CHAIR)

    assert any("Р&amp;Д" in (text or "") for text in notices.texts)
    assert not any("Р&Д" in (text or "") for text in notices.texts)


async def _until_waiting_on_a_lock(engine: AsyncEngine) -> None:
    stmt = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() AND wait_event_type = 'Lock'",
    )
    for _ in range(100):
        async with engine.connect() as connection:
            if await connection.scalar(stmt):
                return
        await asyncio.sleep(0.05)
    pytest.fail("Синхронизация карточки не дождалась блокировки чата")


async def test_a_card_is_rendered_after_the_chat_lock_is_taken(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
    bot_engine: AsyncEngine,
) -> None:
    chat_id, _, group_id = await _grouped_chat(bot_session, client)
    bot_session.add(
        ChatCard(chat_id=chat_id, kind=ChatCardKind.GROUP, ref_id=group_id, mid="c-1"),
    )
    await bot_session.commit()

    async with AsyncSession(bind=bot_engine) as mover:
        await ChatsRepo(mover).lock(chat_id)
        sync = asyncio.create_task(
            _run(
                task_broker,
                sync_chat_card,
                kind=ChatCardKind.GROUP,
                ref_id=group_id,
                post=False,
            ),
        )
        await _until_waiting_on_a_lock(bot_engine)
        await mover.execute(
            update(requests_table)
            .where(requests_table.c.group_id == group_id)
            .values(status=RequestStatus.IN_PROGRESS),
        )
        await mover.commit()
        await sync

    [edited] = pin_api.edited
    assert edited["text"] == texts.group_card(
        RequestCategory.LEAK,
        2,
        RequestStatus.IN_PROGRESS,
    )


async def test_a_shared_request_card_reaches_the_chat_without_the_flat(
    client: BotClient,
    task_broker: InMemoryBroker,
    pin_api: _PinApi,
    bot_session: AsyncSession,
) -> None:
    chat_id = await _bound_chat(bot_session, client)
    chat = await ChatsRepo(bot_session).get(chat_id)
    assert chat is not None
    assert chat.house_id is not None
    flat = Flat(house_id=chat.house_id, number="987")
    bot_session.add(flat)
    await bot_session.flush()
    request = Request(
        house_id=chat.house_id,
        flat_id=flat.id,
        category=RequestCategory.ELEVATOR,
        description="Кв. 987, лифт стоит",
        status=RequestStatus.ACCEPTED,
        channel=RequestChannel.MINIAPP,
        deadline_at=datetime.now(UTC),
    )
    bot_session.add(request)
    await bot_session.flush()
    request_id = request.id
    await bot_session.commit()

    await _run(
        task_broker,
        sync_chat_card,
        kind=ChatCardKind.REQUEST,
        ref_id=request_id,
        post=True,
    )

    [sent] = pin_api.sent
    assert sent["chat_id"] == chat_id
    assert sent["text"].startswith(f"🛗 Заявка №{request_id} · Лифт\nСтатус: принята")
    assert "987" not in sent["text"]
    assert await _cards(bot_session, chat_id) == ["list-1"]


@pytest.mark.usefixtures("recognized")
async def test_a_meter_photo_past_the_yandex_quota_is_not_recognized(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(YandexQuota, "take", lambda _self, _user_id: False)
    meter_id = await _meter_owner(bot_session, client, message_manager)

    await _recognized_card(bot_session, client, task_broker, meter_id)

    assert METER_MANUAL_TEXT in _text(message_manager)
    assert METER_UNREADABLE_TEXT not in _text(message_manager)


@pytest.mark.usefixtures("instant_retries")
async def test_a_voice_outside_a_draft_never_transcribed_asks_for_text(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    await client.send("/start")
    _reread(fake_bot, monkeypatch, [None])

    await _run(
        task_broker,
        transcribe_voice,
        user_id=(await _user(bot_session, client)).id,
        mid="voice-1",
        draft=NewRequestData().to_data(),
        in_draft=False,
    )

    assert notices.texts[-1] == VOICE_FAILED
    assert GREETING in _text(message_manager)


async def test_a_meter_photo_with_no_dialog_open_waits_for_recognition(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    meter_id = await _meter_owner(bot_session, client, message_manager)
    expired = BotClient(
        client.dp,
        user_id=client.user.id,
        chat_id=_max_id(),
        bot=client.bot,
    )

    await _send_photo(expired, None)

    assert _text(message_manager) == METER_WAIT_TEXT
    queued = bot_broker.enqueued(TaskName.RECOGNIZE_METER_PHOTO)[-1]
    assert queued["data"]["meter_id"] == meter_id


@pytest.mark.usefixtures("recognized")
async def test_a_meter_photo_without_ocr_keys_asks_for_the_number(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(VisionClient, "configured", property(lambda _self: False))
    meter_id = await _meter_owner(bot_session, client, message_manager)

    await _recognized_card(bot_session, client, task_broker, meter_id)
    assert METER_MANUAL_TEXT in _text(message_manager)
    assert METER_UNREADABLE_TEXT not in _text(message_manager)
    await client.send("123,4")

    assert "123,400 м³" in _text(message_manager)


async def test_video_from_both_draft_windows_reaches_the_created_request(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    task_broker: InMemoryBroker,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    await client.click(message_manager.last_message(), NEW_REQUEST)
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
    video = VideoAttachment(
        payload=MediaAttachmentPayload(token=str(1), url=RESULT_URL),
    )
    await _send(client, video)
    assert "🎬 Видео: 1" in _text(message_manager)
    await client.send("Течет с потолка")
    await _send(client, video)
    assert "🎬 Видео: 2" in _text(message_manager)
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)
    kwargs = bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1]
    assert kwargs["video_tokens"] == [str(1), str(1)]
    details = AsyncMock(
        return_value=VideoAttachmentDetails(
            token=str(1),
            duration=5,
            width=10,
            height=10,
            urls=VideoUrls(mp4_480=RESULT_URL),
        ),
    )
    download = AsyncMock(
        side_effect=lambda _url, out, **_: out.write(b"\x00\x00\x00\x18ftypmp42"),
    )
    monkeypatch.setattr(fake_bot, "get_video_attachment_details", details)
    monkeypatch.setattr(fake_bot, "download", download)
    await _run(task_broker, create_bot_request, **kwargs)
    user = await _user(bot_session, client)
    stmt = select(Request).where(requests_table.c.author_user_id == user.id)
    request = (await bot_session.execute(stmt)).scalar_one()
    attachments = await RequestsRepo(bot_session).list_attachments(request.id)
    assert len(attachments) == 2
    assert all(attachment.path.endswith(".mp4") for attachment in attachments)
    assert f"Заявка №{request.id} отправлена" in _text(message_manager)


async def test_executor_gets_video_on_send_only(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_id = await _executor_on(bot_session, client, RequestStatus.ACCEPTED)
    user = await _user(bot_session, client)
    user_id = user.id
    name = photo_name().replace(".jpg", ".mp4")
    await RequestsRepo(bot_session).add_attachment(
        request_id,
        name,
        RequestAttachmentKind.ISSUE,
        user.id,
    )
    await bot_session.commit()
    send = AsyncMock()
    monkeypatch.setattr(MaxSender, "send_video", send)
    await _run(task_broker, send_executor_card, request_id=request_id)
    assert "🎬 Видео: 1" in _text(message_manager)
    assert not any(
        isinstance(item, (PhotoAttachment, VideoAttachment))
        for item in message_manager.last_message().body.attachments or []
    )
    send.assert_awaited_once()
    assert send.call_args.args[0].name == name
    await client.click(message_manager.last_message(), DEPART)
    await _run(task_broker, send_executor_card, request_id=request_id, user_id=user_id)
    send.assert_awaited_once()


def _speechkit(
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
    *,
    configured: bool = True,
) -> tuple[list[str], list[bytes]]:
    downloaded: list[str] = []
    heard: list[bytes] = []

    async def download(url: str, destination: BinaryIO) -> BinaryIO:
        downloaded.append(url)
        destination.write(b"OggS-voice")
        return destination

    async def recognize(_self: SpeechClient, audio: bytes) -> str:
        heard.append(audio)
        return VOICE

    monkeypatch.setattr(fake_bot, "download", download)
    monkeypatch.setattr(SpeechClient, "recognize", recognize)
    monkeypatch.setattr(
        SpeechClient,
        "configured",
        property(lambda _self: configured),
    )
    return downloaded, heard


@pytest.mark.usefixtures("instant_retries")
async def test_a_voice_max_left_untranscribed_is_recognized_by_speechkit(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
    bot_session: AsyncSession,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    _reread(fake_bot, monkeypatch, [None])
    downloaded, heard = _speechkit(fake_bot, monkeypatch)

    await _run(
        task_broker,
        transcribe_voice,
        user_id=(await _user(bot_session, client)).id,
        mid="voice-1",
        draft=NewRequestData(category=next(iter(RequestCategory))).to_data(),
        in_draft=True,
    )

    assert downloaded == ["https://max.test/voice.ogg"]
    assert heard == [b"OggS-voice"]
    assert _text(message_manager) == ATTACHMENTS_TEXT.format(attachments=0)
    await client.click(message_manager.last_message(), NEXT)
    assert VOICE in _text(message_manager)


@pytest.mark.usefixtures("instant_retries")
@pytest.mark.parametrize(("configured", "quota_left"), [(False, True), (True, False)])
async def test_a_voice_skips_speechkit_without_keys_or_quota(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
    bot_session: AsyncSession,
    configured: bool,
    quota_left: bool,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    _reread(fake_bot, monkeypatch, [None])
    downloaded, heard = _speechkit(fake_bot, monkeypatch, configured=configured)
    monkeypatch.setattr(YandexQuota, "take", lambda _self, _user_id: quota_left)

    await _run(
        task_broker,
        transcribe_voice,
        user_id=(await _user(bot_session, client)).id,
        mid="voice-1",
        draft=NewRequestData(category=next(iter(RequestCategory))).to_data(),
        in_draft=True,
    )

    assert downloaded == []
    assert heard == []
    assert _text(message_manager).startswith(VOICE_FAILED)


CANCEL_REQUEST = InlineButtonTextLocator("↩️ Отменить заявку")
BY_MISTAKE = InlineButtonTextLocator("↩️ Подана по ошибке")


async def _sent_request(
    session: AsyncSession,
    client: BotClient,
    message_manager: MockMessageManager,
    task_broker: InMemoryBroker,
    bot_broker: RecordingBroker,
) -> Request:
    await _resident_of_a_connected_house(session, client, message_manager)
    await _draft_request(client, message_manager)
    await _run(
        task_broker,
        create_bot_request,
        **bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1],
    )
    user = await _user(session, client)
    stmt = select(Request).where(requests_table.c.author_user_id == user.id)
    return (await session.execute(stmt)).scalar_one()


async def test_a_sent_request_is_canceled_from_the_same_message(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    notices: _RecordingBot,
) -> None:
    request = await _sent_request(
        bot_session,
        client,
        message_manager,
        task_broker,
        bot_broker,
    )

    await client.click(message_manager.last_message(), CANCEL_REQUEST)
    assert _text(message_manager) == CANCEL_TEXT.format(request_id=request.id)
    assert "↩️ Другое" not in _button_texts(message_manager.last_message())
    await client.click(message_manager.last_message(), BY_MISTAKE)

    canceled = await _status(bot_session, request.id)
    assert canceled.status is RequestStatus.DONE
    assert canceled.completion_reason is RequestCompletionReason.RESIDENT_CANCELED
    assert notices.texts == [f"↩️ Заявка №{request.id} отменена"]
    assert _opened(notices.buttons[-1]) == [(OPEN_REQUEST, f"/requests/{request.id}")]
    assert GREETING in _text(message_manager)


async def test_a_request_under_review_is_not_canceled_from_the_bot(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
    answers: _CallbackAnswers,
) -> None:
    request_id = (
        await _sent_request(
            bot_session,
            client,
            message_manager,
            task_broker,
            bot_broker,
        )
    ).id
    await client.click(message_manager.last_message(), CANCEL_REQUEST)
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(status=RequestStatus.ON_REVIEW)
    )
    await bot_session.execute(stmt)
    await bot_session.commit()

    await client.click(message_manager.last_message(), BY_MISTAKE)

    assert answers.notifications == [CANCEL_TOO_LATE]
    assert (await _status(bot_session, request_id)).status is RequestStatus.ON_REVIEW
    assert _text(message_manager) == CANCEL_TEXT.format(request_id=request_id)


async def test_a_photo_with_a_caption_gives_the_rejection_its_text_and_photo(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    request_id = await _reviewing(bot_session, client, task_broker)
    await client.click(message_manager.last_message(), REJECT)
    await _rendered(message_manager, REJECTION_TEXT)

    await _send_photo(client, "Кран все еще течет")
    await client.click(message_manager.last_message(), SEND)

    assert bot_broker.enqueued(TaskName.REJECT_BOT_REQUEST)[-1] == {
        "user_id": (await _user(bot_session, client)).id,
        "request_id": request_id,
        "comment": "Кран все еще течет",
        "photo_urls": [RESULT_URL],
    }


async def test_a_rejection_of_paperwork_is_sent_without_a_photo(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    request_id = await _reviewing(bot_session, client, task_broker)
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(category=RequestCategory.CHARGE_DISPUTE)
    )
    await bot_session.execute(stmt)
    await bot_session.commit()
    await client.click(message_manager.last_message(), REJECT)
    await _rendered(message_manager, REJECTION_TEXT)

    await client.send("Перерасчет так и не сделали")
    assert _text(message_manager) == OPTIONAL_PHOTO_TEXT
    await client.click(message_manager.last_message(), SEND)
    await _run(
        task_broker,
        reject_bot_request,
        **bot_broker.enqueued(TaskName.REJECT_BOT_REQUEST)[-1],
    )

    [repeat] = await _repeats_of(bot_session, request_id)
    assert repeat.description == "Перерасчет так и не сделали"


async def test_an_unexpected_failure_of_a_bot_rejection_still_answers(
    client: BotClient,
    task_broker: InMemoryBroker,
    bot_session: AsyncSession,
    notices: _RecordingBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_id = await _reviewing(bot_session, client, task_broker)

    async def broken(*_: Any, **__: Any) -> None:
        raise RuntimeError(PROBE_DENIED)

    monkeypatch.setattr(RequestsService, "reject", broken)
    task: Any = reject_bot_request
    sent = await (
        task.kicker()
        .with_broker(task_broker)
        .kiq(
            user_id=(await _user(bot_session, client)).id,
            request_id=request_id,
            comment="Кран все еще течет",
            photo_urls=[],
        )
    )
    result = await sent.wait_result(timeout=5)

    assert result.is_err
    assert notices.texts[-1] == NOT_REJECTED_UNEXPECTED


async def test_a_photo_without_a_caption_waits_for_the_rejection_text(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _reviewing(bot_session, client, task_broker)
    await client.click(message_manager.last_message(), REJECT)
    await _rendered(message_manager, REJECTION_TEXT)

    await _send_photo(client, None)
    assert _text(message_manager).startswith(REJECTION_TEXT)
    assert PHOTOS_TEXT.format(photos=1) in _text(message_manager)
    await client.send("Кран все еще течет")

    assert _text(message_manager).startswith(REJECTION_PHOTO_TEXT)
    assert SEND.find_button(message_manager.last_message()) is not None


async def test_the_author_answers_a_question_of_the_management_in_the_bot(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    request_id = await _questioned(
        bot_session,
        client,
        "Под вами 45 или 47 квартира?",
        RequestStatus.ACCEPTED,
    )
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(question_asked_at=datetime.now(UTC))
    )
    await bot_session.execute(stmt)
    await bot_session.commit()

    await _run(task_broker, send_question_card, request_id=request_id)
    card = _text(message_manager)
    assert card.startswith(f"❓ УК уточняет по заявке №{request_id} · Протечка")
    assert "Под вами 45 или 47 квартира?" in card
    await client.click(message_manager.last_message(), InlineButtonTextLocator(ANSWER))
    await _rendered(message_manager, ANSWER_TEXT)
    await client.send("47")

    request = await _status(bot_session, request_id)
    assert request.question_asked_at is None
    assert request.resident_answered_at is not None
    messages = await RequestsRepo(bot_session).list_messages(request_id)
    assert (messages[-1].author_role, messages[-1].text) == ("resident", "47")
    assert ANSWER_SENT in notices.texts
    assert _opened(notices.buttons[-1]) == [(OPEN_REQUEST, f"/requests/{request_id}")]
    assert GREETING in _text(message_manager)


async def _questioned(
    session: AsyncSession,
    client: BotClient,
    question: str,
    status: RequestStatus,
) -> RequestId:
    author = await _started(session, client)
    _, house_id = await _org_house(session)
    session.add(Resident(user_id=author, house_id=house_id, role=ResidentRole.OWNER))
    request_id = await _request(session, house_id, status, author=author)
    session.add(
        RequestMessage(
            request_id=request_id,
            author_user_id=author,
            author_role="staff",
            text=question,
        ),
    )
    await session.commit()
    return request_id


async def test_a_long_question_is_cut_to_fit_a_max_message(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    request_id = await _questioned(
        bot_session,
        client,
        f"<&>{'😀' * 2500}",
        RequestStatus.ACCEPTED,
    )

    await _run(task_broker, send_question_card, request_id=request_id)

    card = _text(message_manager)
    assert len(card.encode("utf-16-le")) // 2 <= texts.MESSAGE_LIMIT
    assert "&lt;&amp;&gt;😀" in card
    assert card.endswith("😀…")


async def test_the_question_card_of_a_closed_request_offers_no_answer(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    request_id = await _questioned(
        bot_session,
        client,
        "Когда вы будете дома?",
        RequestStatus.DONE,
    )

    await _run(task_broker, send_question_card, request_id=request_id)

    assert "Когда вы будете дома?" in _text(message_manager)
    assert _button_texts(message_manager.last_message()) == [OPEN_REQUEST]


async def test_a_short_danger_phrase_opens_the_emergency_screen_not_the_menu(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _consented(client, message_manager)
    phone = "+7 (000) 111-22-33"
    house_id, _ = await _bot_house(
        bot_session,
        org_id=await _org(bot_session, emergency_phone=phone),
    )
    await _linked(bot_session, client, house_id, datetime.now(UTC))

    await client.send("Пахнет газом")

    assert _text(message_manager) == "\n\n".join(
        [
            EMERGENCY_TEXT,
            EMERGENCY_PHONE_TEXT.format(emergency_phone=phone),
            CALL_NOTE_TEXT,
        ],
    )


async def test_a_short_danger_phrase_with_no_window_open_opens_the_emergency_screen(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    users = UsersRepo(bot_session)
    user = await users.upsert_by_max_id(MaxUserId(client.user.id), "Житель", None)
    await users.set_consent(user.id, CONSENT_VERSION)
    await bot_session.commit()

    await client.send("Искрит щиток")

    assert _text(message_manager) == (
        f"{EMERGENCY_TEXT}\n\n{NO_EMERGENCY_PHONE_TEXT}\n\n{CALL_NOTE_TEXT}"
    )


async def test_a_danger_phrase_puts_the_warning_above_the_categories(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    await _consented(client, message_manager)
    phone = "+7 (000) 111-22-33"
    house_id, address = await _bot_house(
        bot_session,
        org_id=await _org(bot_session, emergency_phone=phone),
    )
    await _linked(bot_session, client, house_id, datetime.now(UTC))
    problem = "Пахнет газом в третьем подъезде у лифта"

    await client.send(problem)

    assert _text(message_manager) == (
        f"{DANGER_TEXTS[DangerKind.GAS]}\n🛠 Аварийная служба дома: {phone}\n"
        f"{DANGER_REQUEST_NOTE}\n\n"
        f"{PROBLEM_TEXT.format(address=address, description=problem)}"
    )
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_HOUSE_BUTTON)
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)
    enqueued = bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1]
    assert enqueued["description"] == problem


@pytest.mark.parametrize(
    "problem",
    ["В доме напротив горит мусорка", "Газом не пахнет, просто холодно"],
)
async def test_a_calm_problem_gets_no_warning(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    problem: str,
) -> None:
    _, address = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )

    await client.send(problem)

    assert _text(message_manager) == PROBLEM_TEXT.format(
        address=address,
        description=problem,
    )


async def test_a_danger_phrase_for_a_house_without_a_connected_org_names_its_phone(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    await _consented(client, message_manager)
    org_id = await _org(bot_session, registered_at=None, phone="+7 (000) 555-00-00")
    house_id, address = await _bot_house(bot_session, org_id=org_id)
    await _linked(bot_session, client, house_id, datetime.now(UTC))

    await client.send("Застряли в лифте между третьим и четвертым")

    assert _text(message_manager) == (
        f"{DANGER_TEXTS[DangerKind.TRAPPED]}\n{NO_EMERGENCY_PHONE_TEXT}\n"
        f"{ORG_PHONE_TEXT.format(org_phone='+7 (000) 555-00-00')}\n\n"
        f"{NOT_CONNECTED_TEXT.format(address=address)}"
    )


async def test_a_danger_phrase_without_consent_gets_the_safety_lines_first(
    client: BotClient,
    message_manager: MockMessageManager,
    notices: _RecordingBot,
) -> None:
    await client.send("Пахнет газом")

    assert notices.texts[-1] == danger_warning(DangerKind.GAS, None)
    assert CONSENT_TEXT in _text(message_manager)


async def test_a_danger_phrase_in_the_menu_without_consent_gets_the_safety_lines(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    user = await _user(bot_session, client)
    user.consent_at = None
    await bot_session.commit()

    await client.send("Дым из подвала")

    assert notices.texts[-1] == danger_warning(DangerKind.FIRE, None)
    assert CONSENT_TEXT in _text(message_manager)


async def test_the_gji_pdf_task_sends_the_complaint_file_to_its_author(
    client: BotClient,
    task_broker: InMemoryBroker,
    bot_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    house_id = await _staff(bot_session, client)
    author = (await _user(bot_session, client)).id
    request_id = await _request(
        bot_session,
        house_id,
        RequestStatus.ACCEPTED,
        author=author,
    )
    send_file = AsyncMock()
    monkeypatch.setattr(MaxSender, "send_file", send_file)

    await _run(task_broker, send_gji_pdf, user_id=author, request_id=request_id)

    send_file.assert_awaited_once()
    user, file, text = send_file.call_args.args
    assert user.id == author
    assert file.file_name == f"zhaloba-{request_id}.pdf"
    assert (await file.read()).startswith(b"%PDF")
    assert text == (
        f"📄 Жалоба по заявке №{request_id} для ГЖИ\n"
        "✍️ Впишите ФИО и адрес, распечатайте и подпишите"
    )


async def test_the_broadcast_marks_every_addressee_in_the_register(
    client: BotClient,
    task_broker: InMemoryBroker,
    bot_session: AsyncSession,
    fake_bot: FakeBot,
    notices: _RecordingBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    house_id = await _staff(bot_session, client)
    ids = {"author": (await _user(bot_session, client)).id}
    refused = _max_id()
    for kind in ("neighbour", "refused", "muted", "stopped"):
        user = User(
            max_user_id=refused if kind == "refused" else _max_id(),
            max_chat_id=MaxChatId(secrets.randbits(40)),
            name="Сосед",
            bot_stopped_at=datetime.now(UTC) if kind == "stopped" else None,
        )
        bot_session.add(user)
        await bot_session.flush()
        ids[kind] = user.id
    await NotificationsRepo(bot_session).set_level(
        ids["muted"],
        NotificationCategory.ANNOUNCEMENTS,
        NotificationLevel.OFF,
    )
    announcement_id = await _announcement(bot_session, house_id, ids["author"])
    bot_session.add_all(
        NoticeDelivery(
            announcement_id=announcement_id,
            user_id=user_id,
            house_id=house_id,
        )
        for user_id in ids.values()
    )
    await bot_session.commit()

    async def send_message(**kwargs: Any) -> Any:
        if kwargs["user_id"] == refused:
            return await _forbidden()
        return await notices.send_message(**kwargs)

    monkeypatch.setattr(fake_bot, "send_message", send_message)
    await _run(
        task_broker,
        broadcast_to_users,
        user_ids=list(ids.values()),
        text="Отключат воду",
        category=NotificationCategory.ANNOUNCEMENTS.value,
        mandatory=False,
        announcement_id=announcement_id,
    )

    stmt = select(
        notice_deliveries_table.c.user_id,
        notice_deliveries_table.c.status,
        notice_deliveries_table.c.at,
    ).where(notice_deliveries_table.c.announcement_id == announcement_id)
    rows = (await bot_session.execute(stmt)).all()
    assert {row.user_id: row.status for row in rows} == {
        ids["author"]: NoticeStatus.DELIVERED,
        ids["neighbour"]: NoticeStatus.DELIVERED,
        ids["refused"]: NoticeStatus.FAILED,
        ids["muted"]: NoticeStatus.MUTED,
        ids["stopped"]: NoticeStatus.BOT_STOPPED,
    }
    assert all(row.at is not None for row in rows)
    assert await _delivered(bot_session, announcement_id) == (2, None)


async def test_the_description_window_warns_about_planned_works_of_the_category(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    house_id, _ = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )
    house = await HousesRepo(bot_session).get(house_id)
    assert house is not None
    assert house.org_id is not None
    until = datetime.now(UTC) + timedelta(hours=2)
    warning = WORKS_TEXT.format(works_until=f"{house.local(until):%H:%M %d.%m}")
    bot_session.add(
        Announcement(
            org_id=house.org_id,
            house_ids=[house_id],
            text="Опрессовка",
            channels=["direct"],
            created_by=(await _user(bot_session, client)).id,
            works_category=RequestCategory.WATER_SUPPLY,
            works_from=datetime.now(UTC) - timedelta(hours=1),
            works_until=until,
        ),
    )
    await bot_session.commit()
    water = CATEGORY_RULES[RequestCategory.WATER_SUPPLY].caption

    await client.send("/start")
    await client.click(message_manager.last_message(), NEW_REQUEST)
    await client.click(message_manager.last_message(), InlineButtonTextLocator(water))
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)

    assert _text(message_manager) == f"{warning}\n\n{DESCRIPTION_TEXT}"
    await client.click(message_manager.last_message(), BACK_BUTTON)
    await client.click(message_manager.last_message(), BACK_BUTTON)
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
    assert _text(message_manager) == DESCRIPTION_TEXT


async def test_a_silent_broadcast_never_rings(
    task_broker: InMemoryBroker,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    user = User(
        max_user_id=_max_id(),
        max_chat_id=MaxChatId(secrets.randbits(40)),
        name="Сосед",
    )
    bot_session.add(user)
    await bot_session.flush()
    user_id = user.id
    await NotificationsRepo(bot_session).set_level(
        user_id,
        NotificationCategory.ANNOUNCEMENTS,
        NotificationLevel.SOUND,
    )
    await bot_session.commit()

    for silent in (False, True):
        await _run(
            task_broker,
            broadcast_to_users,
            user_ids=[user_id],
            text="✅ Работы завершены: Водоснабжение",
            category=NotificationCategory.ANNOUNCEMENTS.value,
            mandatory=False,
            silent=silent,
        )

    assert notices.notifies == [True, False]


TOO_MANY = MaxBotTooManyRequestsError(code="too.many.requests", error="", message="")


def _sender_levels(caplog: pytest.LogCaptureFixture) -> list[int]:
    return [
        record.levelno
        for record in caplog.records
        if record.name == "zheka.infra.max.sender"
    ]


@pytest.mark.parametrize("second", [None, TOO_MANY])
async def test_a_card_edit_is_retried_once_after_429(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    second: MaxBotTooManyRequestsError | None,
) -> None:
    monkeypatch.setattr("zheka.infra.max.sender.RETRY_AFTER_429", 0)
    bot = AsyncMock(spec=Bot)
    bot.edit_message = AsyncMock(side_effect=[TOO_MANY, second])
    sender = MaxSender(bot, cast(BgManagerFactory, None))

    with caplog.at_level(logging.WARNING, logger="zheka.infra.max.sender"):
        done = await sender.edit_message(MaxChatId(-70), "mid-1", "🏢 Карточка", [])

    assert done is (second is None)
    assert bot.edit_message.await_count == 2
    assert _sender_levels(caplog) == (
        [logging.WARNING] if second is None else [logging.WARNING, logging.ERROR]
    )


async def test_a_message_is_retried_once_after_429(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr("zheka.infra.max.sender.RETRY_AFTER_429", 0)
    sent = object()
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock(side_effect=[TOO_MANY, sent])
    sender = MaxSender(bot, cast(BgManagerFactory, None))

    with caplog.at_level(logging.WARNING, logger="zheka.infra.max.sender"):
        result = await sender.send_message("📢 Объявление", chat_id=MaxChatId(-70))

    assert result is sent
    assert bot.send_message.await_count == 2
    assert _sender_levels(caplog) == [logging.WARNING]


@pytest.mark.parametrize("is_demo", [False, True])
async def test_the_register_pdf_task_sends_the_register_file_to_the_admin(
    client: BotClient,
    task_broker: InMemoryBroker,
    bot_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    is_demo: bool,
) -> None:
    house_id = await _staff(bot_session, client)
    admin = (await _user(bot_session, client)).id
    house = await HousesRepo(bot_session).get(house_id)
    assert house is not None
    org_id = house.org_id
    assert org_id is not None
    org = await OrgsRepo(bot_session).get(org_id)
    assert org is not None
    org.is_demo = is_demo
    announcement_id = await _announcement(bot_session, house_id, admin)
    stmt = select(announcements_table.c.created_at).where(
        announcements_table.c.id == announcement_id,
    )
    created_at = (await bot_session.execute(stmt)).scalar_one()
    await bot_session.refresh(house)
    send_file = AsyncMock()
    monkeypatch.setattr(MaxSender, "send_file", send_file)
    drawn: list[str] = []
    monkeypatch.setattr(PdfDocument, "text", lambda *args: drawn.append(args[-1]))

    await _run(
        task_broker,
        send_register_pdf,
        user_id=admin,
        org_id=org_id,
        announcement_id=announcement_id,
        house_id=house_id,
        unmarked_only=False,
    )

    send_file.assert_awaited_once()
    user, file, text = send_file.call_args.args
    assert user.id == admin
    assert file.file_name == f"reestr-{announcement_id}.pdf"
    assert (await file.read()).startswith(b"%PDF")
    assert text == (
        "📄 Реестр уведомлений по объявлению от "
        f"{house.local(created_at):%d.%m.%Y}\n"
        f"🏠 {house.address}"
    )
    assert set(drawn) == ({"ДЕМО"} if is_demo else set())


IN_FLAT_BUTTON = InlineButtonTextLocator(IN_FLAT)


IN_HOUSE_BUTTON = InlineButtonTextLocator(IN_HOUSE)


LIFT = InlineButtonTextLocator(CATEGORY_RULES[RequestCategory.ELEVATOR].caption)


async def _created_place(session: AsyncSession, client: BotClient) -> RequestPlace:
    user = await _user(session, client)
    stmt = select(Request).where(requests_table.c.author_user_id == user.id)
    return (await session.execute(stmt)).scalar_one().place


async def test_a_leak_asks_where_the_problem_is_before_the_description(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    await client.send("/start")
    await client.click(message_manager.last_message(), NEW_REQUEST)
    await client.click(message_manager.last_message(), FIRST_CATEGORY)

    assert _text(message_manager) == PLACE_TEXT
    assert _button_texts(message_manager.last_message()) == [
        IN_FLAT,
        IN_HOUSE,
        "⬅️ Назад",
        "🏠 Меню",
    ]
    await client.click(message_manager.last_message(), IN_HOUSE_BUTTON)
    assert DESCRIPTION_TEXT in _text(message_manager)
    await client.send("Течет с крыши в подъезде")
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)

    enqueued = bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1]
    assert enqueued["place"] == RequestPlace.HOUSE
    await _run(task_broker, create_bot_request, **enqueued)
    assert await _created_place(bot_session, client) is RequestPlace.HOUSE


async def test_a_lift_request_does_not_ask_where_the_problem_is(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    await client.send("/start")
    await client.click(message_manager.last_message(), NEW_REQUEST)
    await client.click(message_manager.last_message(), LIFT)

    assert DESCRIPTION_TEXT in _text(message_manager)
    await client.send("Лифт стоит между этажами")
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)

    await _run(
        task_broker,
        create_bot_request,
        **bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1],
    )
    assert await _created_place(bot_session, client) is RequestPlace.HOUSE


async def test_a_free_text_draft_asks_where_then_goes_to_the_attachments(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    await client.send("/start")
    await client.send("Течет кран на кухне уже второй час")
    await client.click(message_manager.last_message(), FIRST_CATEGORY)

    assert _text(message_manager) == PLACE_TEXT
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
    assert _text(message_manager) == ATTACHMENTS_TEXT.format(attachments=0)
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)

    enqueued = bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1]
    assert enqueued["place"] == RequestPlace.FLAT


@pytest.mark.usefixtures("instant_retries")
async def test_a_late_voice_transcript_keeps_the_chosen_place(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    _reread(fake_bot, monkeypatch, [VOICE])
    draft = NewRequestData(category=RequestCategory.LEAK, place=RequestPlace.HOUSE)

    await _run(
        task_broker,
        transcribe_voice,
        user_id=(await _user(bot_session, client)).id,
        mid="voice-1",
        draft=draft.to_data(),
        in_draft=True,
    )
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)

    enqueued = bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1]
    assert enqueued["place"] == RequestPlace.HOUSE


async def test_the_executor_card_says_where_the_problem_is(
    client: BotClient,
    task_broker: InMemoryBroker,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
) -> None:
    request_id = await _executor_on(bot_session, client, RequestStatus.ACCEPTED)
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(place=RequestPlace.HOUSE)
    )
    await bot_session.execute(stmt)
    await bot_session.commit()

    await _run(task_broker, send_executor_card, request_id=request_id)

    assert REQUEST_PLACE_LINES[RequestPlace.HOUSE] in _text(message_manager)


async def test_back_from_the_description_returns_to_the_place_asked_for_the_category(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    bot_broker: RecordingBroker,
) -> None:
    await _resident_of_a_connected_house(bot_session, client, message_manager)
    await client.send("/start")
    await client.click(message_manager.last_message(), NEW_REQUEST)
    await client.click(message_manager.last_message(), FIRST_CATEGORY)
    await client.click(message_manager.last_message(), IN_HOUSE_BUTTON)

    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert _text(message_manager) == PLACE_TEXT
    await client.click(message_manager.last_message(), BACK_BUTTON)
    await client.click(message_manager.last_message(), LIFT)
    await client.click(message_manager.last_message(), BACK_BUTTON)
    assert "🛠 Что случилось?" in _text(message_manager)

    await client.click(
        message_manager.last_message(),
        InlineButtonTextLocator(CATEGORY_RULES[RequestCategory.HEATING].caption),
    )
    assert _text(message_manager) == PLACE_TEXT
    await client.click(message_manager.last_message(), IN_FLAT_BUTTON)
    await client.send("Холодные батареи в комнате")
    await client.click(message_manager.last_message(), NEXT)
    await client.click(message_manager.last_message(), SEND)

    enqueued = bot_broker.enqueued(TaskName.CREATE_BOT_REQUEST)[-1]
    assert enqueued["category"] == RequestCategory.HEATING
    assert enqueued["place"] == RequestPlace.FLAT


async def test_an_unrecognized_text_with_no_window_open_gets_a_hint_and_the_menu(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    users = UsersRepo(bot_session)
    user = await users.upsert_by_max_id(MaxUserId(client.user.id), "Житель", None)
    await users.set_consent(user.id, CONSENT_VERSION)
    await bot_session.commit()
    house_id, address = await _bot_house(bot_session, org_id=await _org(bot_session))
    await _linked(bot_session, client, house_id, datetime.now(UTC))

    await client.send("Привет")

    assert notices.texts[-1] == NOT_UNDERSTOOD
    assert _text(message_manager) == HOUSE_MENU_TEXT.format(address=address)


async def test_an_unrecognized_text_in_the_menu_gets_a_hint(
    client: BotClient,
    message_manager: MockMessageManager,
    bot_session: AsyncSession,
    notices: _RecordingBot,
) -> None:
    _, address = await _resident_of_a_connected_house(
        bot_session,
        client,
        message_manager,
    )
    await client.send("/start")

    await client.send("Спасибо")

    assert notices.texts[-1] == NOT_UNDERSTOOD
    assert _text(message_manager) == HOUSE_MENU_TEXT.format(address=address)


async def test_a_text_without_consent_gets_no_hint(
    client: BotClient,
    message_manager: MockMessageManager,
    notices: _RecordingBot,
) -> None:
    await client.send("Привет")

    assert NOT_UNDERSTOOD not in notices.texts
    assert CONSENT_TEXT in _text(message_manager)
