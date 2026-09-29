from datetime import UTC, datetime

from dishka.integrations.taskiq import FromDishka, inject
from taskiq import async_shared_broker

from zheka.broker.task_names import TaskName
from zheka.core.services.digest import DigestService


@async_shared_broker.task(
    task_name=TaskName.SEND_WEEKLY_DIGESTS.value,
    schedule=[{"cron": "0 * * * *"}],
)
@inject(patch_module=True)
async def send_weekly_digests(digest_service: FromDishka[DigestService]) -> int:
    return await digest_service.send_weekly(datetime.now(UTC))
