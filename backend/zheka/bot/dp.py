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
    access_dialog,
    chat_binding_dialog,
    chats_router,
    commands_router,
    consent_dialog,
    deeplinks_router,
    error_router,
    executor_dialog,
    fallback_router,
    lifecycle_router,
    menu_dialog,
    onboarding_dialog,
    request_dialog,
    review_dialog,
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

# висит на общем родителе: не пройдя фильтр, роутер до детей не спускается.
# На Dialog его вешать нельзя - filter() присваивает и затер бы IntentFilter
PRIVATE_ONLY = MagicData(F.update_context.chat_type == ChatType.DIALOG)


class BotSetup(ZhekaType):
    # фабрику отдает только setup_dialogs, другую собрать нельзя
    dp: Dispatcher
    bg_manager_factory: BgManagerFactory


def make_dispatcher(
    config: RedisConfig,
    storage: BaseStorage | None = None,
    message_manager: MessageManagerProtocol | None = None,
) -> BotSetup:
    key_builder = DefaultKeyBuilder(with_destiny=True)
    events_isolation: BaseEventIsolation | None = None
    if storage is None:
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
        # межпроцессная: два нажатия одного жителя попадают в разные воркеры
        events_isolation = storage.create_isolation()

    dp = Dispatcher(
        storage=storage,
        # контекст диалога запирает events_isolation из setup_dialogs, а
        # сырого состояния FSM у бота нет
        events_isolation=DisabledEventIsolation(),
        key_builder=key_builder,
    )

    dp.update.middleware.outer(LoggingMiddleware())
    dp.message_created.middleware.outer(ThrottlingMiddleware())
    dp.message_callback.middleware.outer(ThrottlingMiddleware())
    # inner: DishkaMiddleware регистрирует setup_dishka позже, outer был бы
    # снаружи контейнера
    dp.update.middleware.inner(TransactionMiddleware())
    # после транзакции, чтобы апсерт попал внутрь той, которая его закоммитит
    dp.update.middleware.inner(UserMiddleware())

    private_router = Router(name="private")
    private_router.message_created.filter(PRIVATE_ONLY)
    private_router.message_callback.filter(PRIVATE_ONLY)
    private_router.bot_started.filter(PRIVATE_ONLY)
    # диплинки раньше команд: у ссылки и у /start один bot_started, а maxo
    # останавливается на первом ответившем. fallback последним
    private_router.include(
        deeplinks_router,
        commands_router,
        consent_dialog,
        menu_dialog,
        onboarding_dialog,
        request_dialog,
        executor_dialog,
        review_dialog,
        chat_binding_dialog,
        access_dialog,
        fallback_router,
    )

    # события жизни бота и чата дома - не окна личного потока
    dp.include(error_router, lifecycle_router, chats_router, private_router)

    media_id_storage = MediaIdStorage()
    factory = setup_dialogs(
        dp,
        message_manager=message_manager
        or ZhekaMessageManager(media_id_storage=media_id_storage),
        media_id_storage=media_id_storage,
        events_isolation=events_isolation,
    )
    return BotSetup(dp=dp, bg_manager_factory=factory)
