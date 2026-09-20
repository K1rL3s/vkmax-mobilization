from datetime import UTC, datetime

from dishka.integrations.taskiq import FromDishka, inject
from taskiq import async_shared_broker

from zheka.broker.task_names import TaskName
from zheka.core.services.requests import RequestsService


@async_shared_broker.task(
    task_name=TaskName.AUTO_CLOSE_REVIEWED_REQUESTS.value,
    schedule=[{"cron": "* * * * *"}],
)
@inject(patch_module=True)
async def auto_close_reviewed_requests(
    requests_service: FromDishka[RequestsService],
) -> int:
    return await requests_service.auto_close(datetime.now(UTC))
