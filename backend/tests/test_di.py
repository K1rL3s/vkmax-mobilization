import asyncio
import contextlib
import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

import aiohttp
import pytest
from dishka import AsyncContainer, Provider
from maxo import Bot
from maxo.bot.api_client import MaxApiClient
from maxo.errors import MaxBotUnauthorizedError
from taskiq import InMemoryBroker

from tests.conftest import empty_bot_setup, make_config

from zheka.api import app as app_module
from zheka.bot import make_engine
from zheka.broker import __main__ as worker
from zheka.config import BotMode, load_config
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


async def _rejected(_: Bot) -> None:
    raise MaxBotUnauthorizedError(
        code="verify.token",
        error="",
        message="Invalid access_token",
    )


@pytest.fixture
def rejected_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Bot, "start", _rejected)
    monkeypatch.setattr(app_module, "setup_logger", lambda _: None)


@pytest.mark.usefixtures("rejected_token")
async def test_a_rejected_token_leaves_the_api_up_without_the_bot_in_polling(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = app_module.app_factory(make_config(), empty_bot_setup())

    async with app.router.lifespan_context(app):
        pass

    assert [
        record.levelno for record in caplog.records if "MAX_TOKEN" in record.message
    ] == [logging.ERROR]


@pytest.mark.usefixtures("rejected_token")
async def test_a_rejected_token_fails_the_webhook_startup() -> None:
    config = make_config()
    config = replace(
        config,
        max=replace(
            config.max,
            mode=BotMode.WEBHOOK,
            webhook_url="https://example.ru/webhook",
            secret_token="webhook-secret",  # noqa: S106
        ),
    )
    app = app_module.app_factory(config, empty_bot_setup())

    with pytest.raises(MaxBotUnauthorizedError):
        async with app.router.lifespan_context(app):
            pass


async def test_a_rejected_token_closes_the_bot_http_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients: list[MaxApiClient] = []

    async def rejected(bot: Bot) -> None:
        clients.append(bot.state.api_client)
        await _rejected(bot)

    monkeypatch.setattr(Bot, "get_my_info", rejected)
    monkeypatch.setattr(app_module, "setup_logger", lambda _: None)
    app = app_module.app_factory(make_config(), empty_bot_setup())

    async with app.router.lifespan_context(app):
        pass

    [client] = clients
    assert client._session.closed  # noqa: SLF001


def test_a_register_code_outside_the_start_param_alphabet_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DEEPLINK_ORG_REGISTER", "reg.code")

    with pytest.raises(ValueError, match="DEEPLINK_ORG_REGISTER"):
        load_config(str(tmp_path / ".env"))


def test_a_webhook_without_a_secret_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for name in ("POSTGRES_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        monkeypatch.setenv(name, "zheka")
    monkeypatch.setenv("MAX_BOT_MODE", "webhook")
    monkeypatch.setenv("MAX_WEBHOOK_URL", "https://example.ru/webhook")
    monkeypatch.setenv("MAX_SECRET_TOKEN", "")

    with pytest.raises(ValueError, match="MAX_SECRET_TOKEN"):
        load_config(str(tmp_path / ".env"))


def test_a_webhook_engine_without_a_secret_is_refused() -> None:
    config = replace(
        make_config().max,
        mode=BotMode.WEBHOOK,
        webhook_url="https://example.ru/webhook",
    )

    with pytest.raises(ValueError, match="MAX_SECRET_TOKEN"):
        make_engine(empty_bot_setup().dp, Bot("test-token"), config)
