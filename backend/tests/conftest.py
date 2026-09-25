import os
import secrets
import tempfile
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
from dishka import AsyncContainer, Provider, Scope
from dishka.integrations.taskiq import ContainerMiddleware
from maxo import Bot, Dispatcher
from maxo.dialogs.manager.bg_manager import BgManagerFactoryImpl
from maxo.dialogs.test_tools import MockMessageManager
from maxo.dialogs.test_tools.bot_client import FakeBot
from maxo.dialogs.test_tools.memory_storage import JsonMemoryStorage
from maxo.integrations.dishka import setup_dishka as setup_maxo_dishka
from maxo.routing.interfaces import BaseRouter
from maxo.routing.signals import BeforeStartup
from sqlalchemy import make_url, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from taskiq import AckableMessage, AsyncBroker, BrokerMessage, InMemoryBroker
from taskiq.message import TaskiqMessage
from testcontainers.postgres import PostgresContainer

from zheka.base import ZhekaType
from zheka.bot import BotSetup, make_dispatcher
from zheka.broker.middlewares import CommitMiddleware
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.config import (
    ApiConfig,
    BotMode,
    Config,
    DbConfig,
    DeeplinksConfig,
    FilesConfig,
    LogConfig,
    LogFormat,
    MaxConfig,
    RedisConfig,
    YandexConfig,
)
from zheka.core.enums import (
    EventType,
    MeterType,
    OrgRole,
    RequestCategory,
    ResidentRole,
    ResidentStatus,
    ServiceType,
    TariffZone,
)
from zheka.core.ids import FlatId, HouseId, MaxUserId, MeterId, OrgId, UserId
from zheka.core.services.admin_requests import AdminRequestsService
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.reminders import RemindersService
from zheka.core.services.request_groups import GroupingService
from zheka.core.services.requests import RequestsService
from zheka.di import make_container
from zheka.di.broker import ZhekaBroker
from zheka.infra.database.models import (
    Event,
    Flat,
    House,
    OrgMember,
    Organization,
    Resident,
    Tariff,
    User,
)
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.notifications import NotificationsRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.reception import ReceptionRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.events import events_table
from zheka.infra.yandex import YandexClassifier

BACKEND_ROOT = Path(__file__).resolve().parent.parent

os.environ.setdefault("MAX_TOKEN", "test-token")
os.environ.setdefault("REDIS_HOST", "127.0.0.1")
os.environ.setdefault("DEEPLINK_ORG_REGISTER", "test-register-code")


def wait_for_postgres(url: str) -> None:
    deadline = time.monotonic() + 30
    dsn = url.replace("postgresql+psycopg://", "postgresql://")
    while True:
        try:
            with psycopg.connect(dsn, connect_timeout=2) as connection:
                connection.execute("SELECT 1")
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.2)
        else:
            return


@pytest.fixture(scope="session")
def database_url() -> Generator[str]:
    with PostgresContainer("postgres:16.9-alpine3.22", driver="psycopg") as postgres:
        os.environ["POSTGRES_HOST"] = postgres.get_container_host_ip()
        os.environ["POSTGRES_PORT"] = str(postgres.get_exposed_port(5432))
        os.environ["POSTGRES_USER"] = postgres.username
        os.environ["POSTGRES_PASSWORD"] = postgres.password
        os.environ["POSTGRES_DB"] = postgres.dbname

        wait_for_postgres(postgres.get_connection_url())
        _migrate()
        yield postgres.get_connection_url()


def _migrate() -> None:
    alembic_cfg = AlembicConfig(str(BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    command.upgrade(alembic_cfg, "head")


@pytest_asyncio.fixture(scope="session")
async def engine(database_url: str) -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    async with engine.connect() as conn:
        transaction = await conn.begin()
        async with AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
        ) as db_session:
            yield db_session
        await transaction.rollback()


class OrgHouseFlatUser(ZhekaType):
    org_id: OrgId
    house_id: HouseId
    flat_id: FlatId
    user_id: UserId


Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


@pytest_asyncio.fixture
async def make_org_house_flat_user(session: AsyncSession) -> Fixture:
    async def _make(
        *,
        org_role: OrgRole | None = None,
        resident_role: ResidentRole | None = None,
        registered: bool = True,
        timezone: str = "Europe/Moscow",
    ) -> OrgHouseFlatUser:
        unique = secrets.token_hex(4)
        org = Organization(
            name=f"УК {unique}",
            inn=secrets.token_hex(6),
            phone="+70000000000",
            address="Тестовая область, Тестоград, Тестовая, 1",
            registered_at=datetime.now(UTC) if registered else None,
            timezone=timezone,
        )
        user = User(max_user_id=MaxUserId(secrets.randbits(48)), name="Тест Тестов")
        session.add_all([org, user])
        await session.flush()

        house = House(
            org_id=org.id,
            region="Тестовая область",
            city="Тестоград",
            street="Тестовая",
            building="1",
            cadastral_no=secrets.token_hex(8),
            chat_binding_code=secrets.token_hex(4),
            timezone=timezone,
        )
        session.add(house)
        await session.flush()

        flat = Flat(house_id=house.id, number="1")
        session.add(flat)
        await session.flush()

        if org_role is not None:
            session.add(OrgMember(org_id=org.id, user_id=user.id, role=org_role))
        if resident_role is not None:
            session.add(
                Resident(
                    user_id=user.id,
                    house_id=house.id,
                    flat_id=flat.id,
                    role=resident_role,
                ),
            )
        await session.flush()

        return OrgHouseFlatUser(
            org_id=org.id,
            house_id=house.id,
            flat_id=flat.id,
            user_id=user.id,
        )

    return _make


def make_config() -> Config:
    return Config(
        log=LogConfig(level="INFO", format=LogFormat.JSON),
        api=ApiConfig(cors=()),
        db=DbConfig(
            host="localhost",
            port=5432,
            user="u",
            password="p",  # noqa: S106
            name="d",
        ),
        redis=RedisConfig(host="localhost", port=6379, password=None, db=0),
        max=MaxConfig(
            token="test-token",  # noqa: S106
            mode=BotMode.POLLING,
            webhook_url=None,
            secret_token=None,
        ),
        files=FilesConfig(
            dir=str(Path(tempfile.gettempdir()) / "zheka-test-files"),
            max_size_mb=10,
        ),
        deeplinks=DeeplinksConfig(org_register="test-register-code"),
        yandex=YandexConfig(api_key=None, folder_id=None),
    )


class RecordingBroker(AsyncBroker):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[TaskiqMessage] = []

    async def kick(self, message: BrokerMessage) -> None:
        self.messages.append(self.formatter.loads(message.message))

    def listen(self) -> AsyncGenerator[bytes | AckableMessage]:
        raise NotImplementedError

    def enqueued(self, task_name: TaskName) -> list[dict[str, Any]]:
        return [
            message.kwargs
            for message in self.messages
            if message.task_name == task_name.value
        ]


@pytest.fixture
def broker() -> RecordingBroker:
    return RecordingBroker()


@pytest.fixture
def publisher(broker: RecordingBroker) -> TaskPublisher:
    return TaskPublisher(broker)


def make_notifications_service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
) -> NotificationsService:
    return NotificationsService(
        NotificationsRepo(session),
        publisher or TaskPublisher(RecordingBroker()),
        EventsService(EventsRepo(session)),
    )


BOT_DB_NAME = "zheka_bot"


def make_bot_config() -> Config:
    return replace(
        make_config(),
        db=DbConfig(
            host=os.environ["POSTGRES_HOST"],
            port=int(os.environ["POSTGRES_PORT"]),
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            name=BOT_DB_NAME,
        ),
    )


@pytest.fixture(scope="session")
def bot_database_url(database_url: str) -> str:
    dsn = database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(f'CREATE DATABASE "{BOT_DB_NAME}"')

    main_db = os.environ["POSTGRES_DB"]
    os.environ["POSTGRES_DB"] = BOT_DB_NAME
    try:
        _migrate()
    finally:
        os.environ["POSTGRES_DB"] = main_db

    url = make_url(database_url).set(database=BOT_DB_NAME)
    return url.render_as_string(hide_password=False)


@pytest_asyncio.fixture(scope="session")
async def bot_engine(bot_database_url: str) -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(bot_database_url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def bot_session(bot_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    async with AsyncSession(bind=bot_engine) as db_session:
        yield db_session


def empty_bot_setup() -> BotSetup:
    dp = Dispatcher()
    return BotSetup(dp=dp, bg_manager_factory=BgManagerFactoryImpl(dp))


def overrides(broker: RecordingBroker, bot: Bot | None = None) -> Provider:
    provider = Provider(scope=Scope.APP)
    provider.provide(lambda: broker, provides=ZhekaBroker, override=True)
    if bot is not None:
        provider.provide(lambda: bot, provides=Bot, override=True)
    return provider


PROBE_ROUTERS: list[BaseRouter] = []


@pytest.fixture(scope="session")
def fake_bot() -> FakeBot:
    return FakeBot()


@pytest.fixture(scope="session")
def message_manager() -> MockMessageManager:
    return MockMessageManager()


@pytest.fixture(scope="session")
def bot_broker() -> RecordingBroker:
    return RecordingBroker()


@pytest.fixture(scope="session")
def bot_setup(message_manager: MockMessageManager) -> BotSetup:
    setup = make_dispatcher(
        make_config().redis,
        storage=JsonMemoryStorage(),
        message_manager=message_manager,
    )
    setup.dp.include(*PROBE_ROUTERS)
    return setup


@pytest_asyncio.fixture(scope="session")
async def bot_container(
    bot_database_url: str,  # noqa: ARG001
    bot_setup: BotSetup,
    bot_broker: RecordingBroker,
    fake_bot: FakeBot,
) -> AsyncGenerator[AsyncContainer]:
    container = make_container(
        overrides(bot_broker),
        config=make_bot_config(),
        bot_setup=bot_setup,
    )
    setup_maxo_dishka(container, bot_setup.dp, auto_inject=True)
    await bot_setup.dp.feed_signal(BeforeStartup(), fake_bot)
    yield container
    await container.close()


@pytest_asyncio.fixture(scope="session")
async def task_broker(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    bot_broker: RecordingBroker,
    fake_bot: FakeBot,
) -> AsyncGenerator[InMemoryBroker]:
    container = make_container(
        overrides(bot_broker, fake_bot),
        config=make_bot_config(),
        bot_setup=bot_setup,
    )
    broker = InMemoryBroker(await_inplace=True).with_middlewares(
        ContainerMiddleware(container),
        CommitMiddleware(),
    )
    yield broker
    await container.close()


def freeze_now(monkeypatch: pytest.MonkeyPatch, module: str, now: datetime) -> None:
    class Frozen(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> Any:
            return now.astimezone(tz)

    monkeypatch.setattr(f"{module}.datetime", Frozen)


@pytest.fixture
async def own(make_org_house_flat_user: Fixture) -> OrgHouseFlatUser:
    return await make_org_house_flat_user(resident_role=ResidentRole.OWNER)


async def add_user(session: AsyncSession, name: str = "Сосед") -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name=name)
    session.add(user)
    await session.flush()
    return user.id


async def add_resident(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    flat_id: FlatId | None,
    *,
    role: ResidentRole = ResidentRole.OWNER,
    verified: bool = True,
    status: ResidentStatus = ResidentStatus.ACTIVE,
    block_reason: str | None = None,
    is_chairman: bool = False,
) -> Resident:
    is_owner = role is ResidentRole.OWNER
    resident = Resident(
        user_id=user_id,
        house_id=house_id,
        flat_id=flat_id,
        role=role,
        can_see_charges=is_owner,
        can_vote=is_owner,
        verified_at=datetime.now(UTC) if verified else None,
        status=status,
        block_reason=block_reason,
        is_chairman=is_chairman,
    )
    session.add(resident)
    await session.flush()
    return resident


def photo_name() -> str:
    return f"{uuid4().hex}.jpg"


async def events_of(session: AsyncSession, type_: EventType) -> list[Event]:
    stmt = select(Event).where(events_table.c.type == type_)
    return list((await session.execute(stmt)).scalars().all())


class StubClassifier(YandexClassifier):
    __slots__ = ("_category",)

    def __init__(self, category: RequestCategory | None) -> None:
        self._category = category

    async def classify(self, text: str) -> RequestCategory | None:  # noqa: ARG002
        return self._category


def requests_service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
    classifier: YandexClassifier | None = None,
) -> RequestsService:
    return RequestsService(
        RequestsRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        UsersRepo(session),
        OrgsRepo(session),
        FilesService(make_config().files, "test-token"),
        GroupingService(RequestsRepo(session), EventsService(EventsRepo(session))),
        make_notifications_service(session, publisher),
        EventsService(EventsRepo(session)),
        classifier or StubClassifier(None),
    )


def admin_requests_service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
) -> AdminRequestsService:
    return AdminRequestsService(
        RequestsRepo(session),
        HousesRepo(session),
        UsersRepo(session),
        OrgsRepo(session),
        ResidentsRepo(session),
        GroupingService(RequestsRepo(session), EventsService(EventsRepo(session))),
        make_notifications_service(session, publisher),
        EventsService(EventsRepo(session)),
    )


def reminders_service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
) -> RemindersService:
    return RemindersService(
        HousesRepo(session),
        OrgsRepo(session),
        MetersRepo(session),
        ResidentsRepo(session),
        PollsRepo(session),
        ChatsRepo(session),
        ReceptionRepo(session),
        EventsRepo(session),
        EventsService(EventsRepo(session)),
        make_notifications_service(session, publisher),
    )


async def add_meter(
    session: AsyncSession,
    flat_id: FlatId,
    *,
    meter_type: MeterType = MeterType.COLD_WATER,
    tariff_zones: int = 1,
    next_verification_date: date | None = None,
) -> MeterId:
    meter = await MetersRepo(session).add(
        flat_id,
        meter_type,
        tariff_zones,
        "SN-0001",
        next_verification_date,
    )
    assert meter is not None
    return meter.id


async def add_reading(
    session: AsyncSession,
    meter_id: MeterId,
    period: date,
    value: int,
    user_id: UserId,
) -> None:
    await MetersRepo(session).add_reading(
        meter_id,
        period,
        {TariffZone.SINGLE: value},
        [photo_name()],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC),
        submitted_by=user_id,
    )


async def add_tariff(
    session: AsyncSession,
    house_id: HouseId,
    value: int,
    service: ServiceType = ServiceType.COLD_WATER,
    valid_from: date = date(2020, 1, 1),
) -> Tariff:
    tariff = Tariff(
        house_id=house_id,
        service=service,
        value=value,
        unit="m3",
        valid_from=valid_from,
    )
    session.add(tariff)
    await session.flush()
    return tariff
