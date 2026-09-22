from collections.abc import Sequence

from maxo.dialogs import Data, DialogManager, ShowMode, StartMode
from maxo.dialogs.api.entities import DEFAULT_STACK_ID, MediaAttachment
from maxo.enums import AttachmentType
from maxo.fsm import State
from maxo.types import MessageCallback

from zheka.bot.dialog_data import MenuData
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
    await dialog_manager.start(
        Menu.main,
        data=MenuData(notice=notice).to_data(),
        mode=StartMode.RESET_STACK,
    )


async def refused(callback: MessageCallback, error: ZhekaError) -> None:
    await callback.callback_answer(notification=str(error))
