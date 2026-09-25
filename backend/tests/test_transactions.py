import secrets
from collections.abc import AsyncGenerator
from contextlib import nullcontext
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from dishka import AsyncContainer, FromDishka
from dishka.integrations.fastapi import DishkaRoute
from dishka.integrations.taskiq import inject as taskiq_inject
from fastapi import APIRouter, FastAPI
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient
from maxo import Router
from maxo.integrations.dishka import inject as maxo_inject
from maxo.routing.signals.update import MaxoUpdate
from maxo.types import ChatTitleChanged, User as MaxUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.pool import QueuePool
from starlette.types import Receive, Scope, Send
from taskiq import InMemoryBroker, async_shared_broker
from taskiq.exceptions import SendTaskError
from taskiq.kicker import AsyncKicker

from tests.conftest import PROBE_ROUTERS, RecordingBroker, empty_bot_setup, overrides

from zheka.api.app import setup_middlewares
from zheka.api.errors import ERROR_RESPONSES, exception_handlers
from zheka.api.middlewares import TRACE_HEADER
from zheka.api.routes.healthcheck import router as healthcheck_router
from zheka.bot import BotSetup
from zheka.broker.task_names import TaskName
from zheka.config import load_config
from zheka.core.enums import NotificationCategory
from zheka.core.errors import EntityNotFound
from zheka.core.ids import MaxUserId, UserId
from zheka.core.services.notifications import NotificationsService
from zheka.di import make_container
from zheka.infra.database.models import User
from zheka.infra.database.tables.users import users_table

FAIL_TITLE = "Уроним обработчик"

probe_router = APIRouter(route_class=DishkaRoute)


async def _write(session: AsyncSession, marker: MaxUserId) -> None:
    session.add(User(max_user_id=marker, name="Проба"))
    await session.flush()


@probe_router.get("/probe/no-database")
async def probe_no_database() -> dict[str, bool]:
    return {"ok": True}


@probe_router.post("/probe/stream")
async def probe_stream(
    marker: int,
    session: FromDishka[AsyncSession],
) -> StreamingResponse:
    await _write(session, MaxUserId(marker))

    async def body() -> AsyncGenerator[bytes]:
        yield b"file-"
        yield b"body"

    return StreamingResponse(body(), media_type="application/octet-stream")


_PROBE_ERRORS: dict[str, type[Exception]] = {
    "not-found": EntityNotFound,
    "value-error": ValueError,
    "unknown": RuntimeError,
}


@probe_router.post("/probe/{outcome}")
async def probe(
    outcome: str,
    marker: int,
    session: FromDishka[AsyncSession],
    notifications: FromDishka[NotificationsService],
) -> dict[str, bool]:
    await _write(session, MaxUserId(marker))
    notifications.notify_user(
        UserId(marker),
        "Уведомление из пробного маршрута",
        category=NotificationCategory.REQUESTS,
        mandatory=True,
    )
    if outcome in _PROBE_ERRORS:
        raise _PROBE_ERRORS[outcome]("проба")
    return {"ok": True}


@pytest_asyncio.fixture
async def probe_container(
    database_url: str,  # noqa: ARG001
    broker: RecordingBroker,
) -> AsyncGenerator[AsyncContainer]:
    container = make_container(
        overrides(broker),
        config=load_config(),
        bot_setup=empty_bot_setup(),
    )
    yield container
    await container.close()


@pytest_asyncio.fixture
async def probe_client(probe_container: AsyncContainer) -> AsyncGenerator[AsyncClient]:
    app = FastAPI(exception_handlers=exception_handlers)
    app.include_router(probe_router, responses=ERROR_RESPONSES)
    app.include_router(healthcheck_router, responses=ERROR_RESPONSES)
    setup_middlewares(app, probe_container, ())
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://probe",
    ) as client:
        yield client


def _marker() -> MaxUserId:
    return MaxUserId(secrets.randbits(48))


async def _committed(engine: AsyncEngine, marker: MaxUserId) -> int:
    async with engine.connect() as connection:
        stmt = select(users_table.c.id).where(users_table.c.max_user_id == marker)
        result = await connection.execute(stmt)
        return len(result.all())


@pytest.mark.parametrize(
    ("path", "status"),
    [("/probe/not-found", 404), ("/probe/value-error", 409)],
)
async def test_handled_error_rolls_back_and_delivers_nothing(
    probe_client: AsyncClient,
    engine: AsyncEngine,
    broker: RecordingBroker,
    path: str,
    status: int,
) -> None:
    marker = _marker()

    response = await probe_client.post(path, params={"marker": marker})

    assert response.status_code == status
    assert response.json()["trace_id"]
    assert response.headers[TRACE_HEADER]
    assert await _committed(engine, marker) == 0
    assert broker.messages == []


async def test_unhandled_error_rolls_the_request_back(
    probe_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    marker = _marker()

    response = await probe_client.post("/probe/unknown", params={"marker": marker})

    assert response.status_code == 500
    assert await _committed(engine, marker) == 0


async def test_failing_commit_persists_and_delivers_nothing(
    probe_client: AsyncClient,
    engine: AsyncEngine,
    broker: RecordingBroker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AsyncSession, "commit", _broken_commit)
    marker = _marker()

    response = await probe_client.post("/probe/ok", params={"marker": marker})

    assert response.status_code == 500
    assert await _committed(engine, marker) == 0
    assert broker.messages == []


async def test_streaming_response_commits_and_still_streams(
    probe_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    marker = _marker()

    response = await probe_client.post("/probe/stream", params={"marker": marker})

    assert response.status_code == 200
    assert response.content == b"file-body"
    assert await _committed(engine, marker) == 1


async def test_request_without_database_work_passes_through(
    probe_client: AsyncClient,
    probe_container: AsyncContainer,
) -> None:
    response = await probe_client.get("/probe/no-database")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    pool = (await probe_container.get(AsyncEngine)).pool
    assert isinstance(pool, QueuePool)
    assert pool.checkedout() == 0
    assert pool.checkedin() == 0


async def test_healthcheck_still_answers(probe_client: AsyncClient) -> None:
    response = await probe_client.get("/healthcheck")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


async def test_successful_request_delivers_exactly_once(
    probe_client: AsyncClient,
    engine: AsyncEngine,
    broker: RecordingBroker,
) -> None:
    marker = _marker()

    response = await probe_client.post("/probe/ok", params={"marker": marker})

    assert response.status_code == 200
    assert await _committed(engine, marker) == 1
    enqueued = broker.enqueued(TaskName.SEND_TO_USER)
    assert len(enqueued) == 1
    assert enqueued[0]["user_id"] == marker


probe_bot_router = Router(name="probe")
PROBE_ROUTERS.append(probe_bot_router)


@probe_bot_router.chat_title_changed()
@maxo_inject
async def probe_bot_handler(
    update: ChatTitleChanged,
    session: FromDishka[AsyncSession],
    notifications: FromDishka[NotificationsService],
) -> None:
    await _write(session, MaxUserId(update.chat_id))
    notifications.notify_user(
        UserId(update.chat_id),
        "Уведомление из обработчика бота",
        category=NotificationCategory.REQUESTS,
        mandatory=True,
    )
    if update.title == FAIL_TITLE:
        raise RuntimeError("обработчик упал")


def _delivered(broker: RecordingBroker, marker: MaxUserId) -> int:
    enqueued = broker.enqueued(TaskName.SEND_TO_USER)
    return [kwargs["user_id"] for kwargs in enqueued].count(marker)


def _bot_update(marker: MaxUserId, title: str) -> MaxoUpdate[ChatTitleChanged]:
    return MaxoUpdate(
        update=ChatTitleChanged(
            timestamp=datetime.now(UTC),
            chat_id=marker,
            title=title,
            user=MaxUser(first_name="Житель", is_bot=False, user_id=_marker()),
        ),
    )


async def test_bot_handler_commits_and_delivers(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    bot_engine: AsyncEngine,
    bot_broker: RecordingBroker,
) -> None:
    marker = _marker()

    await bot_setup.dp.feed_max_update(_bot_update(marker, "Дом на Тестовой"))

    assert await _committed(bot_engine, marker) == 1
    assert _delivered(bot_broker, marker) == 1


async def _broken_commit(self: AsyncSession) -> None:  # noqa: ARG001
    raise RuntimeError("коммит не прошел")


@pytest.mark.parametrize("failure", ["handler", "commit"])
async def test_failed_bot_handler_leaves_nothing(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    bot_engine: AsyncEngine,
    bot_broker: RecordingBroker,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    marker = _marker()
    if failure == "commit":
        monkeypatch.setattr(AsyncSession, "commit", _broken_commit)

    title = FAIL_TITLE if failure == "handler" else "Дом на Тестовой"
    await bot_setup.dp.feed_max_update(_bot_update(marker, title))

    assert await _committed(bot_engine, marker) == 0
    assert _delivered(bot_broker, marker) == 0


async def test_a_request_leaves_the_worker_state_alone(
    probe_container: AsyncContainer,
) -> None:
    app = FastAPI()
    app.include_router(probe_router)
    setup_middlewares(app, probe_container, ())
    worker_state: dict[str, object] = {}

    async def gunicorn_worker(scope: Scope, receive: Receive, send: Send) -> None:
        await app({**scope, "state": worker_state}, receive, send)

    async with AsyncClient(
        transport=ASGITransport(app=gunicorn_worker),
        base_url="http://probe",
    ) as client:
        response = await client.get("/probe/no-database")

    assert response.json() == {"ok": True}
    assert worker_state == {}


@async_shared_broker.task(task_name="probe_task")
@taskiq_inject(patch_module=True)
async def probe_task(
    marker: int,
    fail: bool,
    session: FromDishka[AsyncSession],
    notifications: FromDishka[NotificationsService],
) -> None:
    await _write(session, MaxUserId(marker))
    notifications.notify_user(
        UserId(marker),
        "Уведомление из пробной задачи",
        category=NotificationCategory.REQUESTS,
        mandatory=True,
    )
    if fail:
        raise RuntimeError("задача упала")


@pytest.mark.parametrize(
    ("failure", "delivered"),
    [(None, 1), ("task", 0), ("commit", 0)],
)
async def test_task_delivers_only_after_its_commit(
    task_broker: InMemoryBroker,
    bot_engine: AsyncEngine,
    bot_broker: RecordingBroker,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
    delivered: int,
) -> None:
    marker = _marker()
    if failure == "commit":
        monkeypatch.setattr(AsyncSession, "commit", _broken_commit)

    kicker: AsyncKicker[..., Any] = probe_task.kicker().with_broker(task_broker)
    with pytest.raises(SendTaskError) if failure == "commit" else nullcontext():
        await kicker.kiq(marker=marker, fail=failure == "task")

    assert await _committed(bot_engine, marker) == delivered
    assert _delivered(bot_broker, marker) == delivered
