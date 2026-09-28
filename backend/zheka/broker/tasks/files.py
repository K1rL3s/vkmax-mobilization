import logging
from datetime import UTC, datetime

from dishka.integrations.taskiq import FromDishka, inject
from taskiq import async_shared_broker

from zheka.broker.task_names import TaskName
from zheka.core.services.retention import RetentionService

logger = logging.getLogger(__name__)


@async_shared_broker.task(
    task_name=TaskName.PURGE_FILES.value,
    schedule=[{"cron": "30 3 * * *"}],
)
@inject(patch_module=True)
async def purge_files(retention_service: FromDishka[RetentionService]) -> int:
    removed = await retention_service.purge(datetime.now(UTC))
    logger.info("Удалено файлов без ссылок: %s", removed)
    return removed
