from html import escape
from typing import Any

from dishka import FromDishka
from maxo.dialogs import DialogManager
from maxo.dialogs.api.entities import DEFAULT_STACK_ID
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import ManagedTextInput
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback, MessageCreated

from zheka.bot.cards import back_to_menu, refused
from zheka.bot.dialog_data import ChatBindingData, HouseItem
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import ChatBinding
from zheka.core.errors import InvalidRequest, ZhekaError
from zheka.core.ids import HouseId, MaxChatId
from zheka.core.services.chats import ChatsService
from zheka.infra.max.sender import is_chat_admin

NO_RIGHTS_YET = "Пока не вижу прав, проверьте и нажмите еще раз"
BOUND_TEXT = "Чат «{title}» привязан, приветствие отправил туда"


async def on_start(_start_data: Any, dialog_manager: DialogManager) -> None:
    ChatBindingData.load_start(dialog_manager).dump(dialog_manager)


async def get_binding(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    # ни одно окно привязки не читает строку chats: окно, которое открыла
    # задача, рисует другая сессия, и незакоммиченной строки она не видит
    data = ChatBindingData.load(dialog_manager)
    return {"title": escape(data.title), "notice": data.notice}


@inject
async def get_houses(
    dialog_manager: DialogManager,
    chats_service: FromDishka[ChatsService],
    **kwargs: Any,
) -> dict[str, Any]:
    houses = await chats_service.bindable_houses(dialog_user_id(dialog_manager))
    return {
        **await get_binding(dialog_manager, **kwargs),
        "houses": [HouseItem(id=house.id, title=house.address) for house in houses],
    }


@inject
async def on_house(
    callback: MessageCallback,
    # Any по той же причине, что в онбординге: overload у inject не разбирает
    # четырехаргументный колбэк с Select
    _select: Any,
    dialog_manager: DialogManager,
    house_id: int,
    chats_service: FromDishka[ChatsService],
) -> None:
    data = ChatBindingData.load(dialog_manager)
    try:
        await chats_service.bind(
            dialog_user_id(dialog_manager),
            MaxChatId(data.chat_id),
            HouseId(house_id),
        )
    except ZhekaError as error:
        await refused(callback, error)
        return
    await dialog_manager.switch_to(ChatBinding.rights)


@inject
async def on_code(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    code: str,
    chats_service: FromDishka[ChatsService],
) -> None:
    data = ChatBindingData.load(dialog_manager)
    try:
        await chats_service.bind_by_code(
            dialog_user_id(dialog_manager),
            MaxChatId(data.chat_id),
            code,
        )
    except InvalidRequest as error:
        # неверный код: окно остается ждать следующий
        with ChatBindingData.proxy(dialog_manager) as binding:
            binding.notice = str(error)
        return
    except ZhekaError as error:
        # чат привязали или удалили, пока окно ждало: в стеке по умолчанию
        # остается меню, а не окно кода, которое глотает каждое сообщение
        await back_to_menu(dialog_manager, str(error))
        return
    with ChatBindingData.proxy(dialog_manager) as binding:
        binding.notice = None
    await dialog_manager.switch_to(ChatBinding.rights)


@inject
async def on_rights(
    callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    chats_service: FromDishka[ChatsService],
) -> None:
    data = ChatBindingData.load(dialog_manager)
    chat_id = MaxChatId(data.chat_id)
    # один вызов известной длины, как отрисовка окна, - не та загрузка
    # неизвестной длины, которую правило вебхука отдает задаче
    is_admin = await is_chat_admin(callback.bot, chat_id)
    try:
        await chats_service.set_admin(chat_id, is_admin)
    except ZhekaError as error:
        if dialog_manager.current_stack().id == DEFAULT_STACK_ID:
            # геттер строку чата не читает, и перерисовка показала бы ту же
            # кнопку, которая уже не сработает, а окно глотало бы сообщения
            await back_to_menu(dialog_manager, str(error))
            return
        await refused(callback, error)
        return
    if not is_admin:
        with ChatBindingData.proxy(dialog_manager) as binding:
            binding.notice = NO_RIGHTS_YET
        return
    if dialog_manager.current_stack().id == DEFAULT_STACK_ID:
        # привязка по коду шла в стеке по умолчанию, и окно без кнопок и
        # ввода глотало бы там каждое сообщение
        await back_to_menu(dialog_manager, BOUND_TEXT.format(title=escape(data.title)))
        return
    await dialog_manager.switch_to(ChatBinding.done)
