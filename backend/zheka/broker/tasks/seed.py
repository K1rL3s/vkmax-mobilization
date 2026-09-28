from datetime import UTC, datetime
from pathlib import Path

from dishka.integrations.taskiq import FromDishka, inject
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import async_shared_broker

from zheka.broker.task_names import TaskName
from zheka.config import FilesConfig
from zheka.core.enums import NotificationCategory
from zheka.core.ids import UserId
from zheka.core.services.demo import DemoService
from zheka.core.services.notifications import NotificationsService
from zheka.seed.demo import seed

SEEDED = "✅ Демо-данные готовы"
ALREADY_SEEDED = "👌 Демо-данные уже есть, ничего не менял"


@async_shared_broker.task(task_name=TaskName.SEED_DEMO.value)
@inject(patch_module=True)
async def seed_demo(
    user_id: UserId,
    session: FromDishka[AsyncSession],
    demo: FromDishka[DemoService],
    files: FromDishka[FilesConfig],
    notifications: FromDishka[NotificationsService],
) -> bool:
    seeded = await seed(session, demo, Path(files.dir), datetime.now(UTC))
    notifications.notify_user(
        user_id,
        SEEDED if seeded else ALREADY_SEEDED,
        category=NotificationCategory.ANNOUNCEMENTS,
        mandatory=True,
    )
    return seeded
