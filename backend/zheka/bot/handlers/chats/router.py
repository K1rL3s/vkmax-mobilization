from dishka import FromDishka
from magic_filter import F
from maxo import Router
from maxo.enums import ChatType, MessageLinkType
from maxo.integrations.magic_filter import MagicData
from maxo.omit import is_defined
from maxo.routing.filters import Command
from maxo.routing.filters.command import CommandObject
from maxo.types import (
    BotAddedToChat,
    BotRemovedFromChat,
    MessageCreated,
    MessageRemoved,
    UserAddedToChat,
)

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.ids import MaxChatId, MaxUserId
from zheka.core.models import User
from zheka.core.services.chats import ChatsService, MessageRef

router = Router(name=__name__)

UNPINNED = "🗑 Убрал из списка закрепленных"


@router.bot_added_to_chat()
async def bot_added_handler(
    update: BotAddedToChat,
    publisher: FromDishka[TaskPublisher],
) -> None:
    publisher.publish(
        TaskName.ON_BOT_ADDED,
        chat_id=update.chat_id,
        is_channel=update.is_channel,
        initiator_max_user_id=update.user.id,
    )


@router.bot_removed_from_chat()
async def bot_removed_handler(
    update: BotRemovedFromChat,
    chats_service: FromDishka[ChatsService],
) -> None:
    await chats_service.on_bot_removed(MaxChatId(update.chat_id))


@router.user_added_to_chat()
async def user_added_handler(
    update: UserAddedToChat,
    chats_service: FromDishka[ChatsService],
) -> None:
    if update.is_channel or update.user.is_bot:
        return
    await chats_service.welcome_member(
        MaxChatId(update.chat_id),
        MaxUserId(update.user.id),
        update.user.first_name,
    )


IN_CHAT = MagicData(F.update_context.chat_type == ChatType.CHAT)


@router.message_created(Command("pin"), IN_CHAT)
async def pin_handler(
    update: MessageCreated,
    command: CommandObject,
    chats_service: FromDishka[ChatsService],
    user: User | None = None,
) -> None:
    await chats_service.pin(
        None if user is None else user.id,
        MaxChatId(update.message.recipient.unsafe_chat_id),
        _replied(update),
        command.args,
    )


@router.message_created(Command("unpin"), IN_CHAT)
async def unpin_handler(
    update: MessageCreated,
    command: CommandObject,
    chats_service: FromDishka[ChatsService],
    user: User | None = None,
) -> None:
    args = (command.args or "").strip()
    unpinned = await chats_service.unpin(
        None if user is None else user.id,
        MaxChatId(update.message.recipient.unsafe_chat_id),
        _replied(update),
        int(args) if args.isdecimal() else None,
    )
    if unpinned:
        await update.reply_text(UNPINNED, notify=False)


@router.message_removed()
async def message_removed_handler(
    update: MessageRemoved,
    chats_service: FromDishka[ChatsService],
) -> None:
    await chats_service.on_message_removed(MaxChatId(update.chat_id), update.message_id)


def _replied(update: MessageCreated) -> MessageRef | None:
    link = update.message.link
    if not is_defined(link) or link.type is not MessageLinkType.REPLY:
        return None
    return MessageRef(mid=link.message.mid, seq=link.message.seq)


@router.message_created(Command("repin"), IN_CHAT)
async def repin_handler(
    update: MessageCreated,
    chats_service: FromDishka[ChatsService],
    user: User | None = None,
) -> None:
    await chats_service.repin(
        None if user is None else user.id,
        MaxChatId(update.message.recipient.unsafe_chat_id),
    )
