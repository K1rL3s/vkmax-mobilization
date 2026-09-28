import logging
from collections.abc import Sequence

from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot
from maxo.types.buttons import InlineButtons
from taskiq import async_shared_broker

from zheka.bot.cards import app_link, open_app
from zheka.broker.task_names import TaskName
from zheka.broker.tasks.chats import recheck_chat_rights
from zheka.core.enums import ChatCardKind, NotificationCategory
from zheka.core.ids import AnnouncementId, MaxChatId, UserId
from zheka.core.services.chats import ChatsService
from zheka.infra.database.repos.announcements import AnnouncementsRepo
from zheka.infra.database.repos.chats import ChatsRepo
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
    keyboard: Sequence[Sequence[InlineButtons]] | None = None,
) -> int:
    recipients = await repo.recipients(user_ids, NotificationCategory(category))
    logger.info("Рассылка %s: получателей %s", category, len(recipients))

    sent = 0
    for recipient in recipients:
        notify = recipient.level.resolve_notify(mandatory=mandatory)
        if notify is None:
            continue
        result = await sender.send_message(
            text,
            user_id=recipient.max_user_id,
            notify=notify,
            keyboard=keyboard,
        )
        if result is not None:
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
    bot: FromDishka[Bot],
    app_button: str | None = None,
    app_path: str | None = None,
) -> int:
    keyboard = None if app_button is None else open_app(bot, app_button, app_path)
    return await _fan_out(
        sender,
        repo,
        [user_id],
        text,
        category,
        mandatory,
        keyboard,
    )


@async_shared_broker.task(task_name=TaskName.BROADCAST_TO_USERS.value)
@inject(patch_module=True)
async def broadcast_to_users(
    user_ids: list[UserId],
    text: str,
    category: str,
    mandatory: bool,
    sender: FromDishka[MaxSender],
    repo: FromDishka[NotificationsRepo],
    bot: FromDishka[Bot],
    announcements_repo: FromDishka[AnnouncementsRepo],
    app_button: str | None = None,
    app_path: str | None = None,
    announcement_id: AnnouncementId | None = None,
) -> int:
    keyboard = None if app_button is None else open_app(bot, app_button, app_path)
    sent = await _fan_out(sender, repo, user_ids, text, category, mandatory, keyboard)
    if announcement_id is not None:
        await announcements_repo.set_delivered(announcement_id, direct=sent)
    return sent


@async_shared_broker.task(task_name=TaskName.BROADCAST_TO_CHATS.value)
@inject(patch_module=True)
async def broadcast_to_chats(
    chat_ids: list[MaxChatId],
    text: str,
    sender: FromDishka[MaxSender],
    bot: FromDishka[Bot],
    chats_service: FromDishka[ChatsService],
    users_repo: FromDishka[UsersRepo],
    announcements_repo: FromDishka[AnnouncementsRepo],
    chats_repo: FromDishka[ChatsRepo],
    app_button: str | None = None,
    app_path: str | None = None,
    announcement_id: AnnouncementId | None = None,
    card_kind: ChatCardKind | None = None,
    card_ref_id: int | None = None,
) -> int:
    keyboard = (
        None
        if app_button is None or app_path is None
        else app_link(bot, app_button, app_path)
    )
    logger.info("Рассылка по чатам: чатов %s", len(chat_ids))
    sent = 0
    for chat_id in chat_ids:
        card = (
            None
            if card_kind is None or card_ref_id is None
            else await chats_repo.get_card(chat_id, card_kind, card_ref_id)
        )
        result = await sender.send_message(
            text,
            chat_id=chat_id,
            notify=False,
            keyboard=keyboard,
            reply_to=None if card is None else card.mid,
        )
        if result is None:
            await recheck_chat_rights(chat_id, bot, chats_service, users_repo, sender)
        else:
            sent += 1

    logger.info("Рассылка по чатам: отправлено %s из %s", sent, len(chat_ids))
    if announcement_id is not None:
        await announcements_repo.set_delivered(announcement_id, chat=sent)
    return sent
