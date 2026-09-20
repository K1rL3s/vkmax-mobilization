import secrets
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import cast

import pytest
import pytest_asyncio
from dishka import AsyncContainer, BaseScope, FromDishka, Provider, Scope, provide
from dishka.integrations.fastapi import DishkaRoute
from dishka.integrations.taskiq import (
    CONTAINER_ID,
    CONTAINER_REGISTRY,
    ContainerMiddleware,
)
from fastapi import APIRouter, FastAPI
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient
from maxo import Dispatcher, Router
from maxo.integrations.dishka import (
    inject as maxo_inject,
    setup_dishka as setup_maxo_dishka,
)
from maxo.routing.signals.update import MaxoUpdate
from maxo.types import ChatTitleChanged, User as MaxUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.pool import QueuePool
from taskiq import TaskiqMessage, TaskiqResult

from tests.conftest import RecordingBroker

from zheka.api.app import setup_middlewares
from zheka.api.errors import ERROR_RESPONSES, exception_handlers
from zheka.api.middlewares import TRACE_HEADER
from zheka.api.routes import healthcheck_router
from zheka.bot import make_dispatcher
from zheka.broker.middlewares import CommitMiddleware
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.config import load_config
from zheka.core.enums import NotificationCategory
from zheka.core.errors import EntityNotFound
from zheka.core.ids import MaxUserId, UserId
from zheka.core.services.notifications import NotificationsService
from zheka.di import make_container
from zheka.di.broker import ZhekaBroker
from zheka.infra.database.models import User
from zheka.infra.database.tables.users import users_table

# каждый маршрут пишет строку со своей меткой и падает по-своему: метка
# остается в базе ровно тогда, когда транзакция закоммичена
FAIL_TITLE = "Уроним обработчик"

probe_router = APIRouter(route_class=DishkaRoute)


async def _write(session: AsyncSession, marker: MaxUserId) -> None:
    session.add(User(max_user_id=marker, name="Проба"))
    await session.flush()


@probe_router.post("/probe/not-found")
async def probe_not_found(
    marker: int,
    session: FromDishka[AsyncSession],
) -> None:
    await _write(session, MaxUserId(marker))
    raise EntityNotFound("нет такого")


@probe_router.post("/probe/value-error")
async def probe_value_error(
    marker: int,
    session: FromDishka[AsyncSession],
) -> None:
    await _write(session, MaxUserId(marker))
    raise ValueError("конфликт состояния")


@probe_router.post("/probe/unknown")
async def probe_unknown(
    marker: int,
    session: FromDishka[AsyncSession],
) -> None:
    await _write(session, MaxUserId(marker))
    raise RuntimeError("что-то сломалось")


@probe_router.post("/probe/ok")
async def probe_ok(marker: int, session: FromDishka[AsyncSession]) -> dict[str, bool]:
    await _write(session, MaxUserId(marker))
    return {"ok": True}


@probe_router.post("/probe/publish-then-fail")
async def probe_publish_then_fail(
    marker: int,
    session: FromDishka[AsyncSession],
    notifications: FromDishka[NotificationsService],
) -> None:
    await _write(session, MaxUserId(marker))
    notifications.notify_user(
        UserId(marker),
        "Уведомление о том, чего не случилось",
        category=NotificationCategory.REQUESTS,
        mandatory=True,
    )
    raise EntityNotFound("нет такого")


@probe_router.post("/probe/publish-then-ok")
async def probe_publish_then_ok(
    marker: int,
    session: FromDishka[AsyncSession],
    notifications: FromDishka[NotificationsService],
) -> dict[str, bool]:
    await _write(session, MaxUserId(marker))
    notifications.notify_user(
        UserId(marker),
        "Уведомление о том, что случилось",
        category=NotificationCategory.REQUESTS,
        mandatory=True,
    )
    return {"ok": True}


@probe_router.get("/probe/no-database")
async def probe_no_database() -> dict[str, bool]:
    return {"ok": True}


@probe_router.post("/probe/stream")
async def probe_stream(
    marker: int,
    session: FromDishka[AsyncSession],
) -> StreamingResponse:
    # отдача файла устроена так же: call_next возвращается раньше, чем тело
    # уедет клиенту, и коммит происходит между этими моментами
    await _write(session, MaxUserId(marker))

    async def body() -> AsyncGenerator[bytes]:
        yield b"file-"
        yield b"body"

    return StreamingResponse(body(), media_type="application/octet-stream")


class _RecordingBrokerProvider(Provider):
    # настоящий TaskPublisher из контейнера, но кикает в память, а не в редис
    scope: BaseScope | None = Scope.APP

    def __init__(self, broker: RecordingBroker) -> None:
        super().__init__()
        self._broker = broker

    @provide(override=True)
    def broker(self) -> ZhekaBroker:
        return cast(ZhekaBroker, self._broker)


@pytest_asyncio.fixture
async def probe_container(
    database_url: str,  # noqa: ARG001
    broker: RecordingBroker,
) -> AsyncGenerator[AsyncContainer]:
    container = make_container(
        _RecordingBrokerProvider(broker),
        config=load_config(),
        context={Dispatcher: Dispatcher()},
    )
    yield container
    await container.close()


@pytest_asyncio.fixture
async def probe_client(
    probe_container: AsyncContainer,
) -> AsyncGenerator[AsyncClient]:
    app = FastAPI(exception_handlers=exception_handlers)
    app.include_router(probe_router, responses=ERROR_RESPONSES)
    app.include_router(healthcheck_router, responses=ERROR_RESPONSES)
    setup_middlewares(app, probe_container, ())
    # raise_app_exceptions=False: необработанное исключение должно дойти до
    # ServerErrorMiddleware и вернуться пятисоткой, а не выпрыгнуть в тест
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://probe",
    ) as client:
        yield client


def _marker() -> MaxUserId:
    return MaxUserId(secrets.randbits(48))


async def _committed(engine: AsyncEngine, marker: MaxUserId) -> int:
    # вторым соединением: сессия запроса к этому моменту уже закрыта, и
    # незакоммиченную строку здесь не видно
    async with engine.connect() as connection:
        stmt = select(users_table.c.id).where(users_table.c.max_user_id == marker)
        result = await connection.execute(stmt)
        return len(result.all())


@pytest.mark.parametrize(
    ("path", "status"),
    [("/probe/not-found", 404), ("/probe/value-error", 409)],
)
async def test_handled_error_rolls_the_request_back(
    probe_client: AsyncClient,
    engine: AsyncEngine,
    path: str,
    status: int,
) -> None:
    marker = _marker()

    response = await probe_client.post(path, params={"marker": marker})

    assert response.status_code == status
    # обработчик ошибок отработал внутри транзакционной прослойки, и trace id
    # в теле есть - порядок стека именно такой, как задуман
    assert response.json()["trace_id"]
    assert response.headers[TRACE_HEADER]
    assert await _committed(engine, marker) == 0


async def test_unhandled_error_rolls_the_request_back(
    probe_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    marker = _marker()

    response = await probe_client.post(
        "/probe/unknown",
        params={"marker": marker},
    )

    assert response.status_code == 500
    assert await _committed(engine, marker) == 0


async def test_successful_request_commits(
    probe_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    marker = _marker()

    response = await probe_client.post("/probe/ok", params={"marker": marker})

    assert response.status_code == 200
    assert await _committed(engine, marker) == 1


async def test_failing_commit_persists_nothing(
    probe_client: AsyncClient,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # последний рубеж: коммит упал уже после обработчика, и запись не должна
    # доехать ни одним путем - ни через прослойку, ни через провайдер
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
    # сессию прослойка достает на каждом запросе: у нетронутой коммит обязан
    # быть пустышкой, а не соединением с базой
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


async def test_failed_request_delivers_nothing(
    probe_client: AsyncClient,
    engine: AsyncEngine,
    broker: RecordingBroker,
) -> None:
    marker = _marker()

    response = await probe_client.post(
        "/probe/publish-then-fail",
        params={"marker": marker},
    )

    assert response.status_code == 404
    assert await _committed(engine, marker) == 0
    assert broker.messages == []


async def test_successful_request_delivers_exactly_once(
    probe_client: AsyncClient,
    engine: AsyncEngine,
    broker: RecordingBroker,
) -> None:
    marker = _marker()

    response = await probe_client.post(
        "/probe/publish-then-ok",
        params={"marker": marker},
    )

    assert response.status_code == 200
    assert await _committed(engine, marker) == 1
    enqueued = broker.enqueued(TaskName.SEND_TO_USER)
    assert len(enqueued) == 1
    assert enqueued[0]["user_id"] == marker


async def test_worker_flushes_after_its_own_commit(
    probe_container: AsyncContainer,
    broker: RecordingBroker,
) -> None:
    # тот же порядок, что у воркера: CommitMiddleware стоит в списке последним,
    # а taskiq зовет post_execute в обратном порядке, поэтому он успевает
    # закоммитить и отправить раньше, чем dishka закроет контейнер
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


@pytest.fixture(scope="module")
def bot_broker() -> RecordingBroker:
    return RecordingBroker()


@pytest_asyncio.fixture(scope="module")
async def bot_dispatcher(
    database_url: str,  # noqa: ARG001
    bot_broker: RecordingBroker,
) -> AsyncGenerator[Dispatcher]:
    # диспетчер в процессе один, поэтому и он, и его контейнер модульные, а
    # тесты различают свои сообщения по метке
    config = load_config()
    container = make_container(
        _RecordingBrokerProvider(bot_broker),
        config=config,
        context={Dispatcher: Dispatcher()},
    )
    # настоящий make_dispatcher: тест обязан краснеть, если прослойку забыли
    # зарегистрировать именно там
    dispatcher = make_dispatcher(config.redis)
    setup_maxo_dishka(container, dispatcher, auto_inject=True)
    dispatcher.include(probe_bot_router)
    yield dispatcher
    await container.close()


def _delivered(broker: RecordingBroker, marker: MaxUserId) -> int:
    return sum(
        1
        for kwargs in broker.enqueued(TaskName.SEND_TO_USER)
        if kwargs["user_id"] == marker
    )


def _bot_update(marker: MaxUserId, title: str) -> MaxoUpdate[ChatTitleChanged]:
    # ровно то, что кладет в диспетчер и лонг-поллинг, и вебхук: сырой апдейт,
    # завернутый в MaxoUpdate, - иначе dp.update со своими мидлварями в
    # разбор не попадает вовсе
    return MaxoUpdate(
        update=ChatTitleChanged(
            timestamp=datetime.now(UTC),
            chat_id=marker,
            title=title,
            user=MaxUser(first_name="Житель", is_bot=False, user_id=marker),
        ),
    )


async def test_bot_handler_commits_and_delivers(
    bot_dispatcher: Dispatcher,
    engine: AsyncEngine,
    bot_broker: RecordingBroker,
) -> None:
    marker = _marker()

    await bot_dispatcher.feed_max_update(_bot_update(marker, "Дом на Тестовой"))

    assert await _committed(engine, marker) == 1
    assert _delivered(bot_broker, marker) == 1


async def test_failed_bot_handler_leaves_nothing(
    bot_dispatcher: Dispatcher,
    engine: AsyncEngine,
    bot_broker: RecordingBroker,
) -> None:
    marker = _marker()

    # feed_max_update логирует и глотает исключение обработчика - ровно как
    # в поллинге, поэтому смотреть надо на базу и на очередь
    await bot_dispatcher.feed_max_update(_bot_update(marker, FAIL_TITLE))

    assert await _committed(engine, marker) == 0
    assert _delivered(bot_broker, marker) == 0
