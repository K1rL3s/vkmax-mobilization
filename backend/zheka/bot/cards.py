from collections.abc import Sequence

from maxo import Bot
from maxo.dialogs import Data, DialogManager, ShowMode, StartMode
from maxo.dialogs.api.entities import DEFAULT_STACK_ID, MediaAttachment
from maxo.dialogs.widgets.kbd import Start
from maxo.dialogs.widgets.text import Const
from maxo.enums import AttachmentType
from maxo.fsm import State
from maxo.omit import Omitted, is_defined
from maxo.routing.middlewares.update_context import UPDATE_CONTEXT_KEY
from maxo.types import MessageCallback
from maxo.types.update_context import UpdateContext

from zheka.bot.states import Menu
from zheka.core.errors import ZhekaError
from zheka.core.models import RequestPhoto
from zheka.core.services.files import FilesService


def photo_media(
    files_service: FilesService,
    photos: Sequence[RequestPhoto],
) -> list[MediaAttachment]:
    return [
        MediaAttachment(AttachmentType.IMAGE, path=files_service.path_of(photo.path))
        for photo in photos
    ]


async def ask_in_default_stack(
    dialog_manager: DialogManager,
    state: State,
    data: Data,
) -> None:
    await dialog_manager.bg(stack_id=DEFAULT_STACK_ID).start(
        state,
        data=data,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.SEND,
    )


async def back_to_menu(dialog_manager: DialogManager, notice: str) -> None:
    bot: Bot = dialog_manager.middleware_data["bot"]
    context: UpdateContext = dialog_manager.middleware_data[UPDATE_CONTEXT_KEY]
    await bot.send_message(
        chat_id=Omitted() if context.chat_id is None else context.chat_id,
        text=notice,
        notify=False,
    )
    await dialog_manager.start(
        Menu.main,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.SEND,
    )


async def refused(callback: MessageCallback, error: ZhekaError) -> None:
    await callback.callback_answer(notification=str(error))


def web_app_name(bot: Bot) -> str | None:
    username = bot.state.info.username
    return username if is_defined(username) else None


TO_MENU = Start(
    Const("🏠 Меню"),
    id="to_menu",
    state=Menu.main,
    mode=StartMode.RESET_STACK,
)


BACK = Const("⬅️ Назад")


CANCEL = Start(
    Const("❌ Отмена"),
    id="cancel",
    state=Menu.main,
    mode=StartMode.RESET_STACK,
)
