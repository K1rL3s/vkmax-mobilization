import logging
from collections.abc import Sequence

from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot
from taskiq import async_shared_broker

from zheka.broker.task_names import TaskName
from zheka.broker.tasks.chats import recheck_chat_rights
from zheka.core.enums import NotificationCategory
from zheka.core.ids import MaxChatId, UserId
from zheka.core.services.chats import ChatsService
from zheka.infra.database.repos.notifications import NotificationsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.max import MaxSender

logger = logging.getLogger(__name__)


async def _fan_out(
    sender: MaxSender,
    repo: NotificationsRepo,
    user_ids: Sequence[UserId],
    text: str,
    category: str,
    mandatory: bool,
) -> int:
    recipients = await repo.recipients(user_ids, NotificationCategory(category))
    logger.info("Рассылка %s: получателей %s", category, len(recipients))

    sent = 0
    for recipient in recipients:
        notify = recipient.level.resolve_notify(mandatory=mandatory)
        if notify is None:
            continue
        await sender.send_message(text, user_id=recipient.max_user_id, notify=notify)
        sent += 1

    logger.info("Рассылка %s: отправлено %s из %s", category, sent, len(recipients))
    return sent


@async_shared_broker.task(task_name=TaskName.SEND_TO_USER.value)
@inject(patch_module=True)
async def send_to_user(
    user_id: UserId,
    text: str,
    category: str,
    mandatory: bool,
    sender: FromDishka[MaxSender],
    repo: FromDishka[NotificationsRepo],
) -> int:
    return await _fan_out(sender, repo, [user_id], text, category, mandatory)


@async_shared_broker.task(task_name=TaskName.BROADCAST_TO_USERS.value)
@inject(patch_module=True)
async def broadcast_to_users(
    user_ids: list[UserId],
    text: str,
    category: str,
    mandatory: bool,
    sender: FromDishka[MaxSender],
    repo: FromDishka[NotificationsRepo],
) -> int:
    return await _fan_out(sender, repo, user_ids, text, category, mandatory)


@async_shared_broker.task(task_name=TaskName.BROADCAST_TO_CHATS.value)
@inject(patch_module=True)
async def broadcast_to_chats(
    chat_ids: list[MaxChatId],
    text: str,
    sender: FromDishka[MaxSender],
    bot: FromDishka[Bot],
    chats_service: FromDishka[ChatsService],
    users_repo: FromDishka[UsersRepo],
) -> int:
    logger.info("Рассылка по чатам: чатов %s", len(chat_ids))
    sent = 0
    for chat_id in chat_ids:
        result = await sender.send_message(text, chat_id=chat_id, notify=False)
        if result is None:
            await recheck_chat_rights(chat_id, bot, chats_service, users_repo, sender)
        else:
            sent += 1

    logger.info("Рассылка по чатам: отправлено %s из %s", sent, len(chat_ids))
    return sent
