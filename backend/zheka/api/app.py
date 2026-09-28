import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from maxo import Bot, Dispatcher
from maxo.errors import MaxBotUnauthorizedError
from maxo.integrations.dishka import setup_dishka as setup_maxo_dishka
from maxo.routing.utils import collect_used_updates

from zheka.__meta__ import API_PREFIX, __version__
from zheka.api.errors import ERROR_RESPONSES, exception_handlers
from zheka.api.middlewares import (
    RequestStateMiddleware,
    request_logging_middleware,
    trace_id_middleware,
    transaction_middleware,
)
from zheka.api.routes import (
    announcements,
    charges,
    demo,
    files,
    flats,
    healthcheck,
    houses,
    map as map_,
    me,
    meters,
    orgs,
    polls,
    reception,
    requests,
)
from zheka.api.routes.admin import (
    analytics as admin_analytics,
    announcements as admin_announcements,
    houses as admin_houses,
    map as admin_map,
    meters as admin_meters,
    orgs as admin_orgs,
    polls as admin_polls,
    reception as admin_reception,
    requests as admin_requests,
)
from zheka.bot import BotSetup, make_dispatcher, make_engine
from zheka.config import BotMode, Config, load_config
from zheka.di import make_container
from zheka.logger import setup_logger

logger = logging.getLogger(__name__)

_TAGS = {
    "Healthcheck": "Проверка связи с базой, без авторизации",
    "Профиль": "Аккаунт, согласие на обработку ПД и уведомления",
    "Дома": "Поиск дома, привязка жителя, карточка дома",
    "Квартиры": "Карточка квартиры, подтверждение, приглашения",
    "Заявки": "Заявки жителя, групповые заявки, приемка работ",
    "Счетчики": "Счетчики квартиры и подача показаний",
    "Начисления": "Тарифы, квитанции, разбор начисления, демо-оплата",
    "Опросы": "Опросы дома, голосование, прогноз кворума",
    "Объявления": "Объявления УК для жителя",
    "Прием и доступ": "Запись на прием и слоты доступа в квартиру",
    "Файлы": "Загрузка фото и отдача файлов с проверкой прав",
    "Организации": "Регистрация УК и коды сотрудников",
    "Демо": "Демо-доступ жителя и сотрудника",
    "Админка: организация": "Карточка УК, настройки, сотрудники, приглашения",
    "Админка: дома": "Дома организации, жители, подтверждения квартир",
    "Админка: карта": "Дома организации на карте: заявки, объявления, опросы, прием",
    "Админка: заявки": "Входящие заявки, статусы, исполнители, группы",
    "Админка: счетчики": "Показания по дому",
    "Админка: объявления": "Объявления организации по домам и каналам",
    "Админка: опросы": "Опросы организации",
    "Админка: прием и доступ": "Часы приема, записи, обратный сбор доступа",
    "Админка: аналитика": "Дашборд, сезон показаний, исполнители, бенчмарк",
}


def app_factory(
    config: Config | None = None,
    bot_setup: BotSetup | None = None,
) -> FastAPI:
    config = config or load_config()
    setup_logger(config.log)

    bot_setup = bot_setup or make_dispatcher(config.redis)
    dp = bot_setup.dp
    container = make_container(config=config, bot_setup=bot_setup)
    setup_maxo_dishka(container, dp, auto_inject=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        try:
            if config.max.mode is BotMode.WEBHOOK:
                engine = make_engine(dp, await container.get(Bot), config.max)
                engine.register(app)
                await engine.on_startup(app)
                await engine.set_webhook(update_types=list(collect_used_updates(dp)))
                logger.info("Вебхук зарегистрирован на %s", config.max.webhook_url)
                yield
                await engine.on_shutdown(app)
            else:
                polling = await start_polling(container, dp)
                yield
                if polling is not None:
                    polling.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await polling
        finally:
            await container.close()

    app = FastAPI(
        title="Жэка Коммуналкин",
        version=__version__,
        openapi_tags=[
            {"name": name, "description": description}
            for name, description in _TAGS.items()
        ],
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        exception_handlers=exception_handlers,
        separate_input_output_schemas=False,
        generate_unique_id_function=lambda route: route.name,
        lifespan=lifespan,
    )

    for module in (
        healthcheck,
        me,
        houses,
        map_,
        flats,
        requests,
        meters,
        charges,
        polls,
        announcements,
        reception,
        orgs,
        demo,
        admin_orgs,
        admin_houses,
        admin_map,
        admin_requests,
        admin_meters,
        admin_announcements,
        admin_polls,
        admin_reception,
        admin_analytics,
    ):
        app.include_router(module.router, prefix=API_PREFIX, responses=ERROR_RESPONSES)

    app.include_router(files.router, responses=ERROR_RESPONSES)

    setup_middlewares(app, container, config.api.cors)

    return app


def setup_middlewares(
    app: FastAPI,
    container: AsyncContainer,
    cors: Sequence[str],
) -> None:
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
    app.add_middleware(RequestStateMiddleware)


async def start_polling(
    container: AsyncContainer,
    dp: Dispatcher,
) -> asyncio.Task[None] | None:
    try:
        bot = await container.get(Bot)
    except MaxBotUnauthorizedError:
        logger.error(  # noqa: TRY400
            "Бот не запущен: MAX отверг токен из MAX_TOKEN. "
            "API и мини-приложение работают без бота",
        )
        return None
    polling = asyncio.create_task(
        dp.start_polling(bot, auto_close_bot=False, drop_pending_updates=True),
    )
    logger.info("Бот работает лонг-поллингом")
    return polling
