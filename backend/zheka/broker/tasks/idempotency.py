import logging
from datetime import UTC, datetime

from dishka.integrations.taskiq import FromDishka, inject
from taskiq import async_shared_broker

from zheka.broker.task_names import TaskName
from zheka.core.services.retention import RetentionService

logger = logging.getLogger(__name__)


@async_shared_broker.task(
    task_name=TaskName.PURGE_IDEMPOTENCY_KEYS.value,
    schedule=[{"cron": "45 3 * * *"}],
)
@inject(patch_module=True)
async def purge_idempotency_keys(
    retention_service: FromDishka[RetentionService],
) -> int:
    removed = await retention_service.purge_keys(datetime.now(UTC))
    logger.info("Удалено ключей идемпотентности: %s", removed)
    return removed
