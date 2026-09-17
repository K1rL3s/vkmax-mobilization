from maxo import Dispatcher

from tests.conftest import make_config

from zheka.di import make_container
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo


async def test_make_container_builds_and_resolves_repos() -> None:
    # STRICT_VALIDATION catches a broken provider graph at container build
    # time - this is what makes that gate worth having, since nothing else
    # in the suite ever builds a real container
    container = make_container(
        config=make_config(),
        context={Dispatcher: Dispatcher()},
    )

    async with container, container() as request_container:
        assert isinstance(await request_container.get(UsersRepo), UsersRepo)
        assert isinstance(await request_container.get(ResidentsRepo), ResidentsRepo)
        assert isinstance(await request_container.get(OrgsRepo), OrgsRepo)
        assert isinstance(await request_container.get(EventsRepo), EventsRepo)
