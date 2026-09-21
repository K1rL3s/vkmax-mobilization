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
    # текст и фото maxo 0.9.0 доставляет только в стек по умолчанию
    # (IntentMiddleware.process_message), а карточка живет в своем. Окно ввода
    # поэтому открывается там, по нажатию самого жителя. bg().start(), а не
    # fg(): _get_fake_user отдает вложенному апдейту настоящего User, его
    # UserMiddleware делает апсерт той же строки users, которую держит еще не
    # закоммиченная транзакция этого нажатия, и fg ждал бы сам себя.
    # SEND: для события диалога в личке maxo выбирает EDIT и переписал бы
    # последнее сообщение стека, которое давно ушло вверх по истории
    await dialog_manager.bg(stack_id=DEFAULT_STACK_ID).start(
        state,
        data=data,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.SEND,
    )


async def back_to_menu(dialog_manager: DialogManager, notice: str) -> None:
    # окно ввода заменило меню в стеке по умолчанию; после ввода там остается
    # меню с итогом, а не окно без кнопок, которое глотает каждое сообщение
    await dialog_manager.start(
        Menu.main,
        data=MenuData(notice=notice).to_data(),
        mode=StartMode.RESET_STACK,
    )


async def refused(callback: MessageCallback, error: ZhekaError) -> None:
    # нажатие на устаревшую карточку: сервис отказал до первой записи, окно
    # перерисуется из геттера и покажет правду, а всплывашка скажет почему
    await callback.callback_answer(notification=str(error))
