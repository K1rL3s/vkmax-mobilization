from maxo import Dispatcher

from zheka.config import (
    ApiConfig,
    BotMode,
    Config,
    DbConfig,
    LogConfig,
    LogFormat,
    MaxConfig,
    RedisConfig,
)
from zheka.di import make_container
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

# dummy config values, no real credentials or network calls involved -
# this test only builds the dishka graph, it never opens a connection
_DUMMY_DB_PASSWORD = "p"  # noqa: S105
_DUMMY_MAX_TOKEN = "test-token"  # noqa: S105


def _make_config() -> Config:
    return Config(
        log=LogConfig(level="INFO", format=LogFormat.JSON),
        api=ApiConfig(host="127.0.0.1", port=8000, workers=1, cors=()),
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
            miniapp_url="https://example.com",
        ),
    )


async def test_make_container_builds_and_resolves_repos() -> None:
    # STRICT_VALIDATION catches a broken provider graph at container build
    # time - this is what makes that gate worth having, since nothing else
    # in the suite ever builds a real container
    container = make_container(
        config=_make_config(),
        context={Dispatcher: Dispatcher()},
    )

    async with container, container() as request_container:
        assert isinstance(await request_container.get(UsersRepo), UsersRepo)
        assert isinstance(await request_container.get(ResidentsRepo), ResidentsRepo)
        assert isinstance(await request_container.get(OrgsRepo), OrgsRepo)
        assert isinstance(await request_container.get(EventsRepo), EventsRepo)
