from dishka import FromDishka
from maxo import Router
from maxo.types import BotAddedToChat, BotRemovedFromChat

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.ids import MaxChatId
from zheka.core.services.chats import ChatsService

router = Router(name=__name__)


@router.bot_added_to_chat()
async def bot_added_handler(
    update: BotAddedToChat,
    publisher: FromDishka[TaskPublisher],
) -> None:
    # название чата, выход из него и окно в личке - вызовы MAX, и решает о
    # них задача, а не вебхук с его тридцатью секундами
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
