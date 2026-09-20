from datetime import timedelta

from magic_filter import F
from maxo import Dispatcher, Router
from maxo.dialogs import BgManagerFactory, setup_dialogs
from maxo.dialogs.api.protocols import MessageManagerProtocol
from maxo.dialogs.context.media_storage import MediaIdStorage
from maxo.enums import ChatType
from maxo.fsm.key_builder import DefaultKeyBuilder
from maxo.fsm.storages.base import BaseEventIsolation, BaseStorage
from maxo.fsm.storages.memory import DisabledEventIsolation
from maxo.fsm.storages.redis import RedisStorage
from maxo.integrations.magic_filter import MagicData

from zheka.base import ZhekaType
from zheka.bot.handlers import (
    commands_router,
    consent_dialog,
    error_router,
    fallback_router,
    menu_dialog,
)
from zheka.bot.message_manager import ZhekaMessageManager
from zheka.bot.middlewares import (
    LoggingMiddleware,
    ThrottlingMiddleware,
    TransactionMiddleware,
    UserMiddleware,
)
from zheka.config import RedisConfig

STATE_TTL = timedelta(days=30)

# бот-администратор чата дома получает и его сообщения, а онбординг в группе
# начинаться не должен. Фильтр висит на общем родителе: Router._trigger, не
# пройдя фильтр обсервера, возвращает UNHANDLED и до детей не спускается,
# поэтому одна эта строка закрывает и роутеры, и диалоги под ней. На сам
# Dialog его вешать нельзя - observer.filter() присваивает, и IntentFilter,
# который Dialog ставит себе сам, был бы молча затерт
PRIVATE_ONLY = MagicData(F.update_context.chat_type == ChatType.DIALOG)


class BotSetup(ZhekaType):
    # фабрику отдает setup_dialogs, и другого способа получить ту самую,
    # с которой зарегистрированы мидлвари диалогов, нет
    dp: Dispatcher
    bg_manager_factory: BgManagerFactory


def make_dispatcher(
    config: RedisConfig,
    storage: BaseStorage | None = None,
    events_isolation: BaseEventIsolation | None = None,
    message_manager: MessageManagerProtocol | None = None,
) -> BotSetup:
    key_builder = DefaultKeyBuilder(with_destiny=True)
    if storage is None:
        redis_storage = RedisStorage.from_url(
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
        storage = redis_storage
        # create_isolation() есть только у RedisStorage, поэтому изоляцию
        # берем отсюда, а не из любого storage: gunicorn держит воркер на
        # ядро, и воркер таскика рисует окна тем же стеком, так что два
        # нажатия одного жителя прилетают в разные процессы
        events_isolation = events_isolation or redis_storage.create_isolation()

    dp = Dispatcher(
        storage=storage,
        # межпроцессную блокировку держит events_isolation, отданная ниже в
        # setup_dialogs: она достается IntentMiddlewareFactory и запирает
        # контекст диалога. Своя изоляция диспетчера была бы вторым замком на
        # тех же ключах уровня FSM, а сырого состояния FSM у бота нет
        events_isolation=DisabledEventIsolation(),
        key_builder=key_builder,
    )

    dp.update.middleware.outer(LoggingMiddleware())
    dp.message_created.middleware.outer(ThrottlingMiddleware())
    dp.message_callback.middleware.outer(ThrottlingMiddleware())
    # inner, а не outer: DishkaMiddleware регистрируется позже, уже из
    # setup_dishka, и outer-мидлварь отсюда оказалась бы снаружи контейнера
    dp.update.middleware.inner(TransactionMiddleware())
    # после транзакции, чтобы апсерт попал внутрь той, которая его закоммитит
    dp.update.middleware.inner(UserMiddleware())

    private_router = Router(name="private")
    private_router.message_created.filter(PRIVATE_ONLY)
    private_router.message_callback.filter(PRIVATE_ONLY)
    private_router.bot_started.filter(PRIVATE_ONLY)
    # fallback последним: он отвечает на все, что не разобрали до него
    private_router.include(
        commands_router,
        consent_dialog,
        menu_dialog,
        fallback_router,
    )

    dp.include(error_router, private_router)

    media_id_storage = MediaIdStorage()
    factory = setup_dialogs(
        dp,
        message_manager=message_manager
        or ZhekaMessageManager(media_id_storage=media_id_storage),
        media_id_storage=media_id_storage,
        events_isolation=events_isolation,
    )
    return BotSetup(dp=dp, bg_manager_factory=factory)
