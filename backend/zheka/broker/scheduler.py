import asyncio
import logging
import sys

from taskiq import TaskiqScheduler, async_shared_broker
from taskiq.cli.common_args import LogLevel
from taskiq.cli.scheduler.args import SchedulerArgs
from taskiq.cli.scheduler.run import run_scheduler
from taskiq.schedule_sources import LabelScheduleSource

from zheka.config import load_config
from zheka.di.broker import make_broker
from zheka.logger import setup_logger

logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()
    setup_logger(config.log)

    scheduler = TaskiqScheduler(
        make_broker(config.redis),
        [LabelScheduleSource(async_shared_broker)],
    )

    logger.info("Старт шедулера")
    try:
        await run_scheduler(
            SchedulerArgs(
                scheduler=scheduler,
                log_level=LogLevel.INFO,
                modules=["zheka.broker.tasks"],
                update_interval=10,
                configure_logging=False,
            ),
        )
    except Exception:
        logger.exception("Ошибка при работе планировщика, конец работы")
        raise
    finally:
        await scheduler.shutdown()
        for source in scheduler.sources:
            await source.shutdown()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
