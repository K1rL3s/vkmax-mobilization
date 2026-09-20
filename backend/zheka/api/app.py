import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from maxo import Bot, Dispatcher
from maxo.dialogs import BgManagerFactory
from maxo.integrations.dishka import setup_dishka as setup_maxo_dishka
from maxo.routing.utils import collect_used_updates

from zheka.__meta__ import API_PREFIX, __version__
from zheka.api.errors import ERROR_RESPONSES, exception_handlers
from zheka.api.middlewares import (
    request_logging_middleware,
    trace_id_middleware,
    transaction_middleware,
)
from zheka.api.routes import (
    admin_analytics_router,
    admin_announcements_router,
    admin_houses_router,
    admin_meters_router,
    admin_orgs_router,
    admin_polls_router,
    admin_reception_router,
    admin_requests_router,
    announcements_router,
    charges_router,
    demo_router,
    files_router,
    flats_router,
    healthcheck_router,
    houses_router,
    me_router,
    meters_router,
    orgs_router,
    polls_router,
    reception_router,
    requests_router,
)
from zheka.bot import BotSetup, make_dispatcher, make_engine
from zheka.config import BotMode, Config, load_config
from zheka.di import make_container
from zheka.logger import setup_logger

logger = logging.getLogger(__name__)


def app_factory(
    config: Config | None = None,
    bot_setup: BotSetup | None = None,
) -> FastAPI:
    config = config or load_config()
    setup_logger(config.log)

    # диспетчер в процессе один: роутеры и диалоги - модульные синглтоны, и
    # второй make_dispatcher поднимет RouterAlreadyIncludedError. Готовый
    # принимается для тестов, которым нужен свой - вместе с фабрикой фоновых
    # менеджеров, которую вернул setup_dialogs
    bot_setup = bot_setup or make_dispatcher(config.redis)
    dp = bot_setup.dp
    container = make_container(
        config=config,
        context={
            Dispatcher: dp,
            BgManagerFactory: bot_setup.bg_manager_factory,
        },
    )
    setup_maxo_dishka(container, dp, auto_inject=True)

    app = FastAPI(
        title="Жэка Коммуналкин",
        version=__version__,
        openapi_tags=[
            {
                "name": "Healthcheck",
                "description": "Проверка связи с базой, без авторизации",
            },
            {
                "name": "Профиль",
                "description": "Аккаунт, согласие на обработку ПД и уведомления",
            },
            {
                "name": "Дома",
                "description": "Поиск дома, привязка жителя, карточка дома",
            },
            {
                "name": "Квартиры",
                "description": "Карточка квартиры, подтверждение, приглашения",
            },
            {
                "name": "Заявки",
                "description": "Заявки жителя, групповые заявки, приемка работ",
            },
            {
                "name": "Счетчики",
                "description": "Счетчики квартиры и подача показаний",
            },
            {
                "name": "Начисления",
                "description": "Тарифы, квитанции, разбор начисления, демо-оплата",
            },
            {
                "name": "Опросы",
                "description": "Опросы дома, голосование, прогноз кворума",
            },
            {
                "name": "Объявления",
                "description": "Объявления УК для жителя",
            },
            {
                "name": "Прием и доступ",
                "description": "Запись на прием и слоты доступа в квартиру",
            },
            {
                "name": "Файлы",
                "description": "Загрузка фото и отдача файлов с проверкой прав",
            },
            {
                "name": "Организации",
                "description": "Регистрация УК и коды сотрудников",
            },
            {
                "name": "Демо",
                "description": "Демо-доступ жителя и сотрудника",
            },
            {
                "name": "Админка: организация",
                "description": "Карточка УК, настройки, сотрудники, приглашения",
            },
            {
                "name": "Админка: дома",
                "description": "Дома организации, жители, подтверждения квартир",
            },
            {
                "name": "Админка: заявки",
                "description": "Входящие заявки, статусы, исполнители, группы",
            },
            {
                "name": "Админка: счетчики",
                "description": "Показания по дому",
            },
            {
                "name": "Админка: объявления",
                "description": "Объявления организации по домам и каналам",
            },
            {
                "name": "Админка: опросы",
                "description": "Опросы организации",
            },
            {
                "name": "Админка: прием и доступ",
                "description": "Часы приема, записи, обратный сбор доступа",
            },
            {
                "name": "Админка: аналитика",
                "description": "Дашборд, сезон показаний, исполнители, бенчмарк",
            },
        ],
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        exception_handlers=exception_handlers,
        separate_input_output_schemas=False,
        generate_unique_id_function=lambda route: route.name,
        lifespan=_lifespan(config, dp, container),
    )

    for router in (
        healthcheck_router,
        me_router,
        houses_router,
        flats_router,
        requests_router,
        meters_router,
        charges_router,
        polls_router,
        announcements_router,
        reception_router,
        orgs_router,
        demo_router,
        admin_orgs_router,
        admin_houses_router,
        admin_requests_router,
        admin_meters_router,
        admin_announcements_router,
        admin_polls_router,
        admin_reception_router,
        admin_analytics_router,
    ):
        app.include_router(router, prefix=API_PREFIX, responses=ERROR_RESPONSES)

    # пути файлов зафиксированы целиком, nginx разводит /api/ и /files/ сам
    app.include_router(files_router, responses=ERROR_RESPONSES)

    setup_middlewares(app, container, config.api.cors)

    return app


def setup_middlewares(
    app: FastAPI,
    container: AsyncContainer,
    cors: Sequence[str],
) -> None:
    # порядок регистрации - это стек наизнанку: зарегистрированный последним
    # оказывается снаружи. transaction_middleware должен быть внутри
    # контейнера dishka (ему нужен request.state.dishka_container) и снаружи
    # обработчиков ошибок, которые живут в ExceptionMiddleware - иначе он не
    # увидит ни контейнера, ни ответа 404. trace_id_middleware остается
    # снаружи логирования и транзакции, чтобы trace id был в каждой строке
    # лога и в каждом теле ошибки
    app.middleware("http")(transaction_middleware)
    app.middleware("http")(request_logging_middleware)
    app.middleware("http")(trace_id_middleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors) or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
        allow_credentials=True,
    )

    setup_dishka(container, app)


def _lifespan(
    config: Config,
    dp: Dispatcher,
    container: AsyncContainer,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        bot = await container.get(Bot)

        if config.max.mode is BotMode.WEBHOOK:
            engine = make_engine(dp, bot, config.max)
            engine.register(app)
            await engine.on_startup(app)
            await engine.set_webhook(update_types=list(collect_used_updates(dp)))
            logger.info("Вебхук зарегистрирован на %s", config.max.webhook_url)
            yield
            await engine.on_shutdown(app)
        else:
            polling = asyncio.create_task(
                dp.start_polling(bot, auto_close_bot=False, drop_pending_updates=True),
            )
            logger.info("Бот работает лонг-поллингом")
            yield
            polling.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await polling

        await container.close()

    return lifespan
