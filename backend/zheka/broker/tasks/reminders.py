import logging
from datetime import UTC, datetime

from dishka.integrations.taskiq import FromDishka, inject
from maxo.dialogs import ShowMode
from taskiq import async_shared_broker

from zheka.bot.dialog_data import AccessSlotsData
from zheka.bot.states import AccessSlots
from zheka.broker.task_names import TaskName
from zheka.broker.tasks.requests import open_card
from zheka.core.ids import AccessRequestId
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.reminders import RemindersService
from zheka.infra.database.repos.access import AccessRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.max import MaxSender

logger = logging.getLogger(__name__)


@async_shared_broker.task(
    task_name=TaskName.REMIND_READINGS.value,
    schedule=[{"cron": "0 * * * *"}],
)
@inject(patch_module=True)
async def remind_readings(reminders_service: FromDishka[RemindersService]) -> int:
    return await reminders_service.remind_readings(datetime.now(UTC))


@async_shared_broker.task(
    task_name=TaskName.REMIND_POLLS.value,
    schedule=[{"cron": "0 * * * *"}],
)
@inject(patch_module=True)
async def remind_polls(reminders_service: FromDishka[RemindersService]) -> int:
    return await reminders_service.remind_polls(datetime.now(UTC))


@async_shared_broker.task(
    task_name=TaskName.CLOSE_EXPIRED_POLLS.value,
    schedule=[{"cron": "0 * * * *"}],
)
@inject(patch_module=True)
async def close_expired_polls(reminders_service: FromDishka[RemindersService]) -> int:
    return await reminders_service.close_expired_polls(datetime.now(UTC))


@async_shared_broker.task(
    task_name=TaskName.WARN_VERIFICATION.value,
    schedule=[{"cron": "0 * * * *"}],
)
@inject(patch_module=True)
async def warn_verification(reminders_service: FromDishka[RemindersService]) -> int:
    return await reminders_service.warn_verification(datetime.now(UTC))


@async_shared_broker.task(
    task_name=TaskName.REMIND_APPOINTMENTS.value,
    schedule=[{"cron": "0 * * * *"}],
)
@inject(patch_module=True)
async def remind_appointments(reminders_service: FromDishka[RemindersService]) -> int:
    return await reminders_service.remind_appointments(datetime.now(UTC))


@async_shared_broker.task(task_name=TaskName.BROADCAST_ACCESS_REQUEST.value)
@inject(patch_module=True)
async def broadcast_access_request(
    access_request_id: AccessRequestId,
    access_repo: FromDishka[AccessRepo],
    residents_repo: FromDishka[ResidentsRepo],
    users_repo: FromDishka[UsersRepo],
    notifications_service: FromDishka[NotificationsService],
    sender: FromDishka[MaxSender],
) -> int:
    targets = await access_repo.list_targets(access_request_id)
    residents = await residents_repo.list_verified_for_flats(
        [target.flat_id for target in targets]
    )
    for resident in residents:
        await open_card(
            users_repo,
            notifications_service,
            sender,
            resident.user_id,
            AccessSlots.pick,
            f"access-{access_request_id}",
            AccessSlotsData(access_request_id=int(access_request_id)).to_data(),
            ShowMode.SEND,
        )
    logger.info("Запрос доступа %s: окон открыто %s", access_request_id, len(residents))
    return len(residents)
