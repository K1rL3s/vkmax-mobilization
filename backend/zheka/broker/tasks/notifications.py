import logging
from collections.abc import Sequence

from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot
from maxo.dialogs import ShowMode
from maxo.errors import MaxBotApiError, MaxBotNetworkError
from taskiq import async_shared_broker

from zheka.bot.dialog_data import ChatBindingData
from zheka.bot.states import ChatBinding
from zheka.broker.task_names import TaskName
from zheka.broker.tasks.chats import chat_stack
from zheka.core.enums import NotificationCategory
from zheka.core.errors import ZhekaError
from zheka.core.ids import MaxChatId, UserId
from zheka.core.notifications import resolve_notify
from zheka.core.services.chats import ChatsService
from zheka.infra.database.repos.notifications import NotificationsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.max import MaxSender
from zheka.infra.max.sender import is_chat_admin

logger = logging.getLogger(__name__)


async def _fan_out(
    sender: MaxSender,
    notifications_repo: NotificationsRepo,
    user_ids: Sequence[UserId],
    text: str,
    category: str,
    mandatory: bool,
) -> int:
    # уровень читается при доставке, а не при постановке в очередь
    recipients = await notifications_repo.recipients(
        user_ids, NotificationCategory(category)
    )
    logger.info("Рассылка %s: получателей %s", category, len(recipients))

    sent = 0
    for recipient in recipients:
        notify = resolve_notify(recipient.level, mandatory=mandatory)
        if notify is None:
            continue
        # недоступного получателя MaxSender проглатывает и возвращает None
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
    notifications_repo: FromDishka[NotificationsRepo],
) -> int:
    return await _fan_out(
        sender, notifications_repo, [user_id], text, category, mandatory
    )


@async_shared_broker.task(task_name=TaskName.BROADCAST_TO_USERS.value)
@inject(patch_module=True)
async def broadcast_to_users(
    user_ids: list[UserId],
    text: str,
    category: str,
    mandatory: bool,
    sender: FromDishka[MaxSender],
    notifications_repo: FromDishka[NotificationsRepo],
) -> int:
    return await _fan_out(
        sender, notifications_repo, user_ids, text, category, mandatory
    )


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
    # у чата нет уровня, notify=False повторяет DEFAULT_LEVEL
    logger.info("Рассылка по чатам: чатов %s", len(chat_ids))
    sent = 0
    for chat_id in chat_ids:
        result = await sender.send_message(text, chat_id=chat_id, notify=False)
        if result is not None:
            sent += 1
            continue

        # события о смене прав MAX не шлет: не ушло - перепроверяем права и
        # зовем того, кто привязывал, на единственную кнопку, которая это чинит
        try:
            is_admin = await is_chat_admin(bot, chat_id)
            chat = await chats_service.set_admin(chat_id, is_admin)
        except (MaxBotApiError, MaxBotNetworkError, ZhekaError):
            logger.exception("Права бота в чате %s не перепроверены", chat_id)
            continue
        binder = (
            None
            if is_admin or chat.bound_by is None
            else await users_repo.get_by_id(chat.bound_by)
        )
        if binder is None:
            continue
        # со звуком: бот без прав глушит весь дом, пока кто-то не нажмет
        await sender.start_dialog(
            ChatBinding.rights,
            binder,
            notify=True,
            data=ChatBindingData(
                chat_id=int(chat_id), title=chat.title or ""
            ).to_data(),
            stack_id=chat_stack(chat_id),
            show_mode=ShowMode.SEND,
        )

    logger.info("Рассылка по чатам: отправлено %s из %s", sent, len(chat_ids))
    return sent
