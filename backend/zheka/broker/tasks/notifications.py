import logging
from collections.abc import Sequence

from dishka.integrations.taskiq import FromDishka, inject
from maxo.types.buttons import InlineButtons
from maxo.types.link_button import LinkButton
from taskiq import async_shared_broker

from zheka.broker.task_names import TaskName
from zheka.core.enums import NotificationCategory
from zheka.core.ids import MaxChatId, UserId
from zheka.core.notifications import Buttons, resolve_notify
from zheka.infra.database.repos.notifications import NotificationsRepo
from zheka.infra.max import MaxSender

logger = logging.getLogger(__name__)


def _keyboard(buttons: Buttons | None) -> list[list[InlineButtons]] | None:
    if not buttons:
        return None
    return [[LinkButton(text=button["text"], url=button["url"])] for button in buttons]


async def _fan_out(
    sender: MaxSender,
    notifications_repo: NotificationsRepo,
    user_ids: Sequence[UserId],
    text: str,
    category: str,
    mandatory: bool,
    buttons: Buttons | None,
) -> int:
    # уровень разрешается здесь, а не на месте вызова: перезапущенная задача
    # видит настройки такими, какие они сейчас, а в очереди лежит только id
    recipients = await notifications_repo.recipients(
        user_ids,
        NotificationCategory(category),
    )
    keyboard = _keyboard(buttons)
    logger.info("Рассылка %s: получателей %s", category, len(recipients))

    sent = 0
    for recipient in recipients:
        notify = resolve_notify(recipient.level, mandatory=mandatory)
        if notify is None:
            continue
        # недоступного получателя MaxSender проглатывает и возвращает None,
        # поэтому один мертвый адресат не обрывает остальную рассылку
        await sender.send_message(
            text,
            user_id=recipient.max_user_id,
            notify=notify,
            keyboard=keyboard,
        )
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
    buttons: Buttons | None,
    sender: FromDishka[MaxSender],
    notifications_repo: FromDishka[NotificationsRepo],
) -> int:
    return await _fan_out(
        sender,
        notifications_repo,
        [user_id],
        text,
        category,
        mandatory,
        buttons,
    )


@async_shared_broker.task(task_name=TaskName.BROADCAST_TO_USERS.value)
@inject(patch_module=True)
async def broadcast_to_users(
    user_ids: list[UserId],
    text: str,
    category: str,
    mandatory: bool,
    buttons: Buttons | None,
    sender: FromDishka[MaxSender],
    notifications_repo: FromDishka[NotificationsRepo],
) -> int:
    return await _fan_out(
        sender,
        notifications_repo,
        user_ids,
        text,
        category,
        mandatory,
        buttons,
    )


@async_shared_broker.task(task_name=TaskName.BROADCAST_TO_CHATS.value)
@inject(patch_module=True)
async def broadcast_to_chats(
    chat_ids: list[MaxChatId],
    text: str,
    buttons: Buttons | None,
    sender: FromDishka[MaxSender],
) -> int:
    # у чата нет ни настроек уровня, ни получателя, чей уровень можно
    # разрешить, поэтому здесь стоит продуктовый дефолт - тот же, что в
    # DEFAULT_LEVEL (NotificationLevel.SILENT): меняя его, поправить и эту
    # строку
    keyboard = _keyboard(buttons)
    logger.info("Рассылка по чатам: чатов %s", len(chat_ids))
    for chat_id in chat_ids:
        await sender.send_message(
            text,
            chat_id=chat_id,
            notify=False,
            keyboard=keyboard,
        )
    logger.info("Рассылка по чатам: отправлено %s", len(chat_ids))
    return len(chat_ids)
