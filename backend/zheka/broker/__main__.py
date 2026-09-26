import asyncio
import logging
import signal
from collections.abc import Coroutine
from typing import Any

from dishka.integrations.taskiq import ContainerMiddleware
from maxo.integrations.dishka import setup_dishka as setup_maxo_dishka
from taskiq import SmartRetryMiddleware, TaskiqScheduler, async_shared_broker
from taskiq.api import run_receiver_task
from taskiq.cli.common_args import LogLevel
from taskiq.cli.scheduler.args import SchedulerArgs
from taskiq.cli.scheduler.run import run_scheduler
from taskiq.schedule_sources import LabelScheduleSource

from zheka.bot import make_dispatcher
from zheka.broker.middlewares import CommitMiddleware, ContextVarsMiddleware
from zheka.broker.tasks import *  # noqa: F403
from zheka.config import load_config
from zheka.di import make_container
from zheka.di.broker import ZhekaBroker, make_broker
from zheka.logger import setup_logger
from zheka.runner import run

logger = logging.getLogger(__name__)


async def _must_not_return(name: str, coro: Coroutine[Any, Any, None]) -> None:
    await coro
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        raise asyncio.CancelledError
    msg = f"{name} завершился штатно, процесс продолжать работу не должен"
    raise RuntimeError(msg)


async def main() -> None:
    config = load_config()
    setup_logger(config.log)

    bot_setup = make_dispatcher(config.redis)
    container = make_container(config=config, bot_setup=bot_setup)
    setup_maxo_dishka(container, bot_setup.dp, auto_inject=True)

    logger.debug("Инициализирую брокер")
    broker = make_broker(config.redis).with_middlewares(
        ContextVarsMiddleware(),
        ContainerMiddleware(container),
        SmartRetryMiddleware(use_delay_exponent=True),
        CommitMiddleware(),
    )

    logger.debug("Инициализирую шедулер")
    scheduler = TaskiqScheduler(
        await container.get(ZhekaBroker),
        [LabelScheduleSource(async_shared_broker)],
    )
    scheduler_args = SchedulerArgs(
        scheduler=scheduler,
        log_level=LogLevel.INFO,
        modules=["zheka.broker.tasks"],
        update_interval=10,
        configure_logging=False,
    )

    broker.is_worker_process = True
    await broker.startup()

    logger.info("Старт приема задач и шедулера")
    try:
        async with asyncio.TaskGroup() as tasks:
            _ = tasks.create_task(
                _must_not_return("Прием задач", run_receiver_task(broker)),
            )
            _ = tasks.create_task(
                _must_not_return("Шедулер", run_scheduler(scheduler_args)),
            )
    except* Exception:
        logger.exception("Прием задач или шедулер упал, конец работы")
        raise
    finally:
        await broker.shutdown()
        await container.close()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    run(main())
