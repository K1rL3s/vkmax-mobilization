import secrets
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from dishka import AsyncContainer, FromDishka
from dishka.integrations.fastapi import DishkaRoute
from dishka.integrations.taskiq import (
    CONTAINER_ID,
    CONTAINER_REGISTRY,
    ContainerMiddleware,
)
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
from taskiq import TaskiqMessage, TaskiqResult

from tests.conftest import (
    PROBE_ROUTERS,
    RecordingBroker,
    RecordingBrokerProvider,
    bot_context,
    empty_bot_setup,
)

from zheka.api.app import setup_middlewares
from zheka.api.errors import ERROR_RESPONSES, exception_handlers
from zheka.api.middlewares import TRACE_HEADER
from zheka.api.routes.healthcheck import router as healthcheck_router
from zheka.bot import BotSetup
from zheka.broker.middlewares import CommitMiddleware
from zheka.broker.publisher import TaskPublisher
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
    bot_setup = empty_bot_setup()
    container = make_container(
        RecordingBrokerProvider(broker),
        config=load_config(),
        context=bot_context(bot_setup),
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


async def test_failing_commit_persists_nothing(
    probe_client: AsyncClient,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _broken_commit(self: AsyncSession) -> None:  # noqa: ARG001
        raise RuntimeError("коммит не прошел")

    monkeypatch.setattr(AsyncSession, "commit", _broken_commit)
    marker = _marker()

    response = await probe_client.post("/probe/ok", params={"marker": marker})

    assert response.status_code == 500
    assert await _committed(engine, marker) == 0


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


async def test_worker_flushes_after_its_own_commit(
    probe_container: AsyncContainer,
    broker: RecordingBroker,
) -> None:
    container_middleware = ContainerMiddleware(probe_container)
    commit_middleware = CommitMiddleware()
    host = RecordingBroker().with_middlewares(container_middleware, commit_middleware)
    message = TaskiqMessage(
        task_id="probe",
        task_name="probe",
        labels={},
        args=[],
        kwargs={},
    )
    message = await container_middleware.pre_execute(message)
    request_container = host.state[CONTAINER_REGISTRY][message.labels[CONTAINER_ID]]
    publisher = await request_container.get(TaskPublisher)
    publisher.publish(TaskName.SEND_TO_USER, user_id=1)

    await commit_middleware.post_execute(
        message,
        TaskiqResult(is_err=False, return_value=None, execution_time=0.0),
    )

    assert len(broker.enqueued(TaskName.SEND_TO_USER)) == 1


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


async def test_failed_bot_handler_leaves_nothing(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_setup: BotSetup,
    bot_engine: AsyncEngine,
    bot_broker: RecordingBroker,
) -> None:
    marker = _marker()

    await bot_setup.dp.feed_max_update(_bot_update(marker, FAIL_TITLE))

    assert await _committed(bot_engine, marker) == 0
    assert _delivered(bot_broker, marker) == 0
