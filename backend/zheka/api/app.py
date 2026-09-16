import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from maxo import Bot, Dispatcher
from maxo.integrations.dishka import setup_dishka as setup_maxo_dishka
from maxo.routing.utils import collect_used_updates

from zheka.__meta__ import API_PREFIX, __version__
from zheka.api.errors import exception_handlers
from zheka.api.middlewares import request_logging_middleware, trace_id_middleware
from zheka.api.routes import healthcheck_router
from zheka.bot import make_dispatcher, make_engine
from zheka.config import BotMode, Config, load_config
from zheka.di import make_container
from zheka.logger import setup_logger

logger = logging.getLogger(__name__)


def app_factory(config: Config | None = None) -> FastAPI:
    config = config or load_config()
    setup_logger(config.log)

    dp = make_dispatcher(config.redis)
    container = make_container(config=config, context={Dispatcher: dp})
    setup_maxo_dishka(container, dp, auto_inject=True)

    app = FastAPI(
        title="Жэка Коммуналкин",
        version=__version__,
        openapi_tags=[
            {
                "name": "Healthcheck",
                "description": "Проверка связи с базой, без авторизации",
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

    app.include_router(healthcheck_router, prefix=API_PREFIX)

    app.middleware("http")(request_logging_middleware)
    app.middleware("http")(trace_id_middleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.api.cors) or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
        allow_credentials=True,
    )

    setup_dishka(container, app)

    return app


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
