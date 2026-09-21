from maxo import Dispatcher
from maxo.dialogs import BgManagerFactory

from tests.conftest import empty_bot_setup, make_config

from zheka.di import make_container
from zheka.infra.database.repos.users import UsersRepo


async def test_make_container_builds_and_resolves_repos() -> None:
    # STRICT_VALIDATION catches a broken provider graph at container build time
    bot_setup = empty_bot_setup()
    container = make_container(
        config=make_config(),
        context={
            Dispatcher: bot_setup.dp,
            BgManagerFactory: bot_setup.bg_manager_factory,
        },
    )

    async with container, container() as request_container:
        assert isinstance(await request_container.get(UsersRepo), UsersRepo)
