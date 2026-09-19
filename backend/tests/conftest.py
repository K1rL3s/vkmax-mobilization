import os
import secrets
import tempfile
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from pathlib import Path

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

from zheka.base import ZhekaType
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
)
from zheka.core.enums import OrgRole, ResidentRole
from zheka.core.ids import FlatId, HouseId, MaxUserId, OrgId, UserId
from zheka.infra.database.models import (
    Flat,
    House,
    OrgMember,
    Organization,
    Resident,
    User,
)

BACKEND_ROOT = Path(__file__).resolve().parent.parent

# load_config() (используемый migrations/env.py) требует эти переменные,
# а тестам не нужен ни настоящий бот, ни редис
os.environ.setdefault("MAX_TOKEN", "test-token")
os.environ.setdefault("REDIS_HOST", "127.0.0.1")
os.environ.setdefault("DEEPLINK_ORG_REGISTER", "test-register-code")


# initdb поднимает временный сервер и печатает в лог то же самое
# "database system is ready to accept connections", по которому testcontainers
# отпускает контейнер, - к этому моменту порт снаружи еще закрыт. Ждем сами,
# иначе alembic ловит connection refused примерно в каждом третьем прогоне
POSTGRES_READY_TIMEOUT = 30.0


def wait_for_postgres(url: str, timeout: float = POSTGRES_READY_TIMEOUT) -> None:
    deadline = time.monotonic() + timeout
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

        alembic_cfg = AlembicConfig(str(BACKEND_ROOT / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
        command.upgrade(alembic_cfg, "head")

        yield postgres.get_connection_url()


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
    ) -> OrgHouseFlatUser:
        unique = secrets.token_hex(4)
        org = Organization(
            name=f"УК {unique}",
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
            street="Тестовая",
            building="1",
            cadastral_no=secrets.token_hex(8),
            chat_binding_code=secrets.token_hex(4),
        )
        session.add(house)
        await session.flush()

        flat = Flat(house_id=house.id, number="1")
        session.add(flat)
        await session.flush()

        user = User(max_user_id=MaxUserId(secrets.randbits(48)), name="Тест Тестов")
        session.add(user)
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


# dummy config values, no real credentials or network calls involved
_DUMMY_DB_PASSWORD = "p"  # noqa: S105
_DUMMY_MAX_TOKEN = "test-token"  # noqa: S105


def make_config() -> Config:
    return Config(
        log=LogConfig(level="INFO", format=LogFormat.JSON),
        api=ApiConfig(cors=()),
        db=DbConfig(
            host="localhost",
            port=5432,
            user="u",
            password=_DUMMY_DB_PASSWORD,
            name="d",
        ),
        redis=RedisConfig(host="localhost", port=6379, password=None, db=0),
        max=MaxConfig(
            token=_DUMMY_MAX_TOKEN,
            mode=BotMode.POLLING,
            webhook_url=None,
            secret_token=None,
        ),
        files=FilesConfig(
            dir=str(Path(tempfile.gettempdir()) / "zheka-test-files"),
            max_size_mb=10,
        ),
        deeplinks=DeeplinksConfig(org_register="test-register-code"),
    )
