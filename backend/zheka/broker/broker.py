import logging

from dishka.integrations.taskiq import ContainerMiddleware
from taskiq import AsyncBroker, SmartRetryMiddleware

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

    container = make_container(config=config)

    logger.debug("Инициализирую брокер")
    return make_broker(config.redis).with_middlewares(
        ContextVarsMiddleware(),
        ContainerMiddleware(container),
        SmartRetryMiddleware(use_delay_exponent=True),
        CommitMiddleware(),
    )
