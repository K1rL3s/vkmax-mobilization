from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot
from maxo.dialogs import ShowMode
from maxo.types.link_button import LinkButton
from maxo.utils.deeplink import create_start_link
from taskiq import async_shared_broker

from zheka.bot.dialog_data import ChatBindingData
from zheka.bot.states import ChatBinding
from zheka.broker.task_names import TaskName
from zheka.core.deeplinks import house_payload
from zheka.core.ids import HouseId, MaxChatId, MaxUserId
from zheka.core.services.chats import ChatsService
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.max import MaxSender

WELCOME_TEXT = (
    "Здравствуйте, соседи! Я бот вашего дома. Сюда буду присылать объявления "
    "УК и напоминания об опросах, а заявки, показания и начисления - в личке "
    "со мной"
)
JOIN_HOUSE = "Присоединиться к дому"


def chat_stack(chat_id: MaxChatId) -> str:
    # стек выводится из чата: повторное окно по тому же чату ложится в него,
    # а не заводит вторую живую копию
    return f"chat-{chat_id}"


@async_shared_broker.task(task_name=TaskName.ON_BOT_ADDED.value)
@inject(patch_module=True)
async def on_bot_added(
    chat_id: MaxChatId,
    is_channel: bool,
    initiator_max_user_id: MaxUserId,
    bot: FromDishka[Bot],
    chats_service: FromDishka[ChatsService],
    users_repo: FromDishka[UsersRepo],
    sender: FromDishka[MaxSender],
) -> None:
    # канал - не чат дома. Инициатор, до которого бот не достучится в личке,
    # чат не привяжет, а больше некому
    user = None if is_channel else await users_repo.get_by_max_id(initiator_max_user_id)
    if user is None or user.max_chat_id is None or user.bot_stopped_at is not None:
        await bot.leave_chat(chat_id=chat_id)
        return

    user_id = user.id
    if await chats_service.bindable_houses(user_id):
        state, stack_id = ChatBinding.house, chat_stack(chat_id)
    elif await chats_service.is_resident(user_id):
        # код ждет текст, а текст maxo доставляет только в стек по
        # умолчанию. Затереть там окно можно: житель только что сам добавил
        # бота и ждет этого сообщения
        state, stack_id = ChatBinding.code, None
    else:
        await bot.leave_chat(chat_id=chat_id)
        return

    chat = await bot.get_chat(chat_id=chat_id)
    title = chat.title or ""
    await chats_service.on_bot_added(chat_id, title)
    await sender.start_dialog(
        state,
        user,
        notify=False,
        data=ChatBindingData(chat_id=int(chat_id), title=title).to_data(),
        stack_id=stack_id,
        show_mode=ShowMode.SEND,
    )


@async_shared_broker.task(task_name=TaskName.WELCOME_CHAT.value)
@inject(patch_module=True)
async def welcome_chat(
    chat_id: MaxChatId,
    house_id: HouseId,
    bot: FromDishka[Bot],
    sender: FromDishka[MaxSender],
) -> None:
    # в группе нет интерактива: одна кнопка-ссылка, а не окно диалога
    await sender.send_message(
        WELCOME_TEXT,
        chat_id=chat_id,
        notify=False,
        keyboard=[
            [
                LinkButton(
                    text=JOIN_HOUSE, url=create_start_link(bot, house_payload(house_id))
                )
            ]
        ],
    )
