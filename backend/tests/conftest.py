import os
import secrets
import tempfile
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
from dishka import AsyncContainer, BaseScope, Provider, Scope, provide
from dishka.integrations.taskiq import ContainerMiddleware
from maxo import Bot, Dispatcher
from maxo.dialogs import BgManagerFactory
from maxo.dialogs.manager.bg_manager import BgManagerFactoryImpl
from maxo.dialogs.test_tools import MockMessageManager
from maxo.dialogs.test_tools.bot_client import FakeBot
from maxo.dialogs.test_tools.memory_storage import JsonMemoryStorage
from maxo.integrations.dishka import setup_dishka as setup_maxo_dishka
from maxo.routing.interfaces import BaseRouter
from maxo.routing.signals import BeforeStartup
from sqlalchemy import make_url
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
from zheka.core.enums import OrgRole, ResidentRole
from zheka.core.ids import FlatId, HouseId, MaxUserId, OrgId, UserId
from zheka.core.services.events import EventsService
from zheka.core.services.notifications import NotificationsService
from zheka.di import make_container
from zheka.di.broker import ZhekaBroker
from zheka.infra.database.models import (
    Flat,
    House,
    OrgMember,
    Organization,
    Resident,
    User,
)
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.notifications import NotificationsRepo

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


@pytest_asyncio.fixture
async def make_org_house_flat_user(
    session: AsyncSession,
) -> Callable[..., Awaitable[OrgHouseFlatUser]]:
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
            org_id=OrgId(org.id),
            house_id=HouseId(house.id),
            flat_id=FlatId(flat.id),
            user_id=UserId(user.id),
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


def bot_context(setup: BotSetup) -> dict[Any, Any]:
    return {Dispatcher: setup.dp, BgManagerFactory: setup.bg_manager_factory}


def empty_bot_setup() -> BotSetup:
    dp = Dispatcher()
    return BotSetup(dp=dp, bg_manager_factory=BgManagerFactoryImpl(dp))


class RecordingBrokerProvider(Provider):
    scope: BaseScope | None = Scope.APP

    def __init__(self, broker: RecordingBroker) -> None:
        super().__init__()
        self._broker = broker

    @provide(override=True)
    def broker(self) -> ZhekaBroker:
        return cast(ZhekaBroker, self._broker)


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
        RecordingBrokerProvider(bot_broker),
        config=make_bot_config(),
        context=bot_context(bot_setup),
    )
    setup_maxo_dishka(container, bot_setup.dp, auto_inject=True)
    await bot_setup.dp.feed_signal(BeforeStartup(), fake_bot)
    yield container
    await container.close()


class FakeBotProvider(Provider):
    scope: BaseScope | None = Scope.APP

    def __init__(self, bot: Bot) -> None:
        super().__init__()
        self._bot = bot

    @provide(override=True)
    def bot(self) -> Bot:
        return self._bot


@pytest_asyncio.fixture(scope="session")
async def task_broker(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    bot_broker: RecordingBroker,
    fake_bot: FakeBot,
) -> AsyncGenerator[InMemoryBroker]:
    container = make_container(
        RecordingBrokerProvider(bot_broker),
        FakeBotProvider(fake_bot),
        config=make_bot_config(),
        context=bot_context(bot_setup),
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
