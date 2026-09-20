from datetime import timedelta

from maxo import Dispatcher
from maxo.fsm.key_builder import DefaultKeyBuilder
from maxo.fsm.storages.memory import DisabledEventIsolation
from maxo.fsm.storages.redis import RedisStorage

from zheka.bot.handlers import start_router
from zheka.bot.middlewares import (
    LoggingMiddleware,
    ThrottlingMiddleware,
    TransactionMiddleware,
)
from zheka.config import RedisConfig

STATE_TTL = timedelta(days=30)


def make_dispatcher(config: RedisConfig) -> Dispatcher:
    key_builder = DefaultKeyBuilder(with_destiny=True)
    storage = RedisStorage.from_url(
        config.url,
        key_builder=key_builder,
        state_ttl=STATE_TTL,
        data_ttl=STATE_TTL,
        connection_kwargs={
            "socket_connect_timeout": 15,
            "socket_timeout": 5,
            "retry_on_timeout": True,
        },
    )

    dp = Dispatcher(
        storage=storage,
        events_isolation=DisabledEventIsolation(),
        key_builder=key_builder,
    )

    dp.update.middleware.outer(LoggingMiddleware())
    dp.message_created.middleware.outer(ThrottlingMiddleware())
    dp.message_callback.middleware.outer(ThrottlingMiddleware())
    # inner, а не outer: DishkaMiddleware регистрируется позже, уже из
    # setup_dishka, и outer-мидлварь отсюда оказалась бы снаружи контейнера
    dp.update.middleware.inner(TransactionMiddleware())

    dp.include(start_router)

    return dp
