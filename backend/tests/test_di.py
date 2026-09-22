from typing import Any

import aiohttp
import pytest
from dishka import AsyncContainer, Provider

from tests.conftest import bot_context, empty_bot_setup, make_config

from zheka.broker import broker as worker
from zheka.di import make_container
from zheka.infra.database.repos.users import UsersRepo


async def test_make_container_builds_and_resolves_repos() -> None:
    bot_setup = empty_bot_setup()
    container = make_container(config=make_config(), context=bot_context(bot_setup))

    async with container, container() as request_container:
        assert isinstance(await request_container.get(UsersRepo), UsersRepo)


async def test_the_worker_closes_the_http_session_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    containers: list[AsyncContainer] = []

    def spy(*providers: Provider, **kwargs: Any) -> AsyncContainer:
        containers.append(make_container(*providers, **kwargs))
        return containers[-1]

    monkeypatch.setattr(worker, "load_config", make_config)
    monkeypatch.setattr(worker, "setup_logger", lambda _: None)
    monkeypatch.setattr(worker, "make_dispatcher", lambda _: empty_bot_setup())
    monkeypatch.setattr(worker, "make_container", spy)
    broker = worker.main()
    broker.is_worker_process = True
    [container] = containers
    http = await container.get(aiohttp.ClientSession)

    await broker.shutdown()

    assert http.closed
