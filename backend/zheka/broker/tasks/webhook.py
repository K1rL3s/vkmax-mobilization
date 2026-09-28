import logging

from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot, Dispatcher
from taskiq import async_shared_broker

from zheka.bot.webhook import make_engine, restore_webhook
from zheka.broker.task_names import TaskName
from zheka.config import BotMode, MaxConfig

logger = logging.getLogger(__name__)


@async_shared_broker.task(
    task_name=TaskName.KEEP_WEBHOOK.value,
    schedule=[{"cron": "*/10 * * * *"}],
)
@inject(patch_module=True)
async def keep_webhook(
    bot: FromDishka[Bot],
    dp: FromDishka[Dispatcher],
    config: FromDishka[MaxConfig],
) -> bool:
    if config.mode is not BotMode.WEBHOOK:
        return False
    restored = await restore_webhook(make_engine(dp, bot, config))
    if restored:
        logger.warning("Вебхука не было в подписках MAX, зарегистрировал заново")
    return restored
