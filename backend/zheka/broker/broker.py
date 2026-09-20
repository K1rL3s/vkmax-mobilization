import logging

from dishka.integrations.taskiq import ContainerMiddleware
from maxo import Dispatcher
from maxo.dialogs import BgManagerFactory
from maxo.integrations.dishka import setup_dishka as setup_maxo_dishka
from taskiq import AsyncBroker, SmartRetryMiddleware

from zheka.bot import make_dispatcher
from zheka.broker.middlewares import CommitMiddleware, ContextVarsMiddleware
from zheka.broker.tasks import *  # noqa: F403
from zheka.config import load_config
from zheka.di import make_container
from zheka.di.broker import make_broker
from zheka.logger import setup_logger

logger = logging.getLogger(__name__)


def main() -> AsyncBroker:
    config = load_config()
    setup_logger(config.log)

    # окно рисует диспетчер того же процесса: фоновый менеджер кормит
    # апдейтом его, а не сеть. Воркер не поллит и не слушает вебхук
    bot_setup = make_dispatcher(config.redis)
    container = make_container(
        config=config,
        context={
            Dispatcher: bot_setup.dp,
            BgManagerFactory: bot_setup.bg_manager_factory,
        },
    )
    setup_maxo_dishka(container, bot_setup.dp, auto_inject=True)

    logger.debug("Инициализирую брокер")
    return make_broker(config.redis).with_middlewares(
        ContextVarsMiddleware(),
        ContainerMiddleware(container),
        SmartRetryMiddleware(use_delay_exponent=True),
        CommitMiddleware(),
    )
