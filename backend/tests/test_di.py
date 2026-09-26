import asyncio
import contextlib
from typing import Any

import aiohttp
import pytest
from dishka import AsyncContainer, Provider
from taskiq import InMemoryBroker

from tests.conftest import empty_bot_setup, make_config

from zheka.broker import __main__ as worker
from zheka.di import make_container


async def test_the_worker_closes_the_http_session_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    containers: list[AsyncContainer] = []
    started = asyncio.Event()

    def spy(*providers: Provider, **kwargs: Any) -> AsyncContainer:
        containers.append(make_container(*providers, **kwargs))
        return containers[-1]

    async def scheduler(_: Any) -> None:
        started.set()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.Event().wait()

    monkeypatch.setattr(worker, "load_config", make_config)
    monkeypatch.setattr(worker, "setup_logger", lambda _: None)
    monkeypatch.setattr(worker, "make_dispatcher", lambda _: empty_bot_setup())
    monkeypatch.setattr(worker, "make_container", spy)
    monkeypatch.setattr(worker, "make_broker", lambda _: InMemoryBroker())
    monkeypatch.setattr(
        worker,
        "run_receiver_task",
        lambda _: asyncio.Event().wait(),
    )
    monkeypatch.setattr(worker, "run_scheduler", scheduler)
    main = asyncio.create_task(worker.main())
    await started.wait()
    [container] = containers
    http = await container.get(aiohttp.ClientSession)

    main.cancel()

    with pytest.raises(asyncio.CancelledError):
        await main
    assert http.closed
