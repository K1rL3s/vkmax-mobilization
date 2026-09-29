import json
from collections.abc import Sequence

from maxo import Bot
from maxo.dialogs import Data, DialogManager, ShowMode, StartMode
from maxo.dialogs.api.entities import DEFAULT_STACK_ID, MediaAttachment
from maxo.dialogs.widgets.kbd import Start
from maxo.dialogs.widgets.text import Const
from maxo.enums import AttachmentType
from maxo.fsm import State
from maxo.omit import Omitted, is_defined
from maxo.routing.filters import Payload
from maxo.routing.middlewares.update_context import UPDATE_CONTEXT_KEY
from maxo.types import MessageCallback, OpenAppButton
from maxo.types.link_button import LinkButton
from maxo.types.update_context import UpdateContext
from maxo.utils.deeplink import create_startapp_link
from maxo.utils.payload import encode_payload

from zheka.bot.states import Menu
from zheka.core.errors import ZhekaError
from zheka.core.models import RequestAttachment
from zheka.core.services.files import FilesService
from zheka.infra.max.sender import keyboard_attachments


def photo_media(
    files_service: FilesService,
    attachments: Sequence[RequestAttachment],
) -> list[MediaAttachment]:
    return [
        MediaAttachment(
            AttachmentType.IMAGE,
            path=files_service.path_of(attachment.path),
        )
        for attachment in attachments
        if not files_service.is_video(attachment.path)
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


async def back_to_menu(
    dialog_manager: DialogManager,
    notice: str,
    app_button: str | None = None,
    app_path: str | None = None,
) -> None:
    bot: Bot = dialog_manager.middleware_data["bot"]
    context: UpdateContext = dialog_manager.middleware_data[UPDATE_CONTEXT_KEY]
    keyboard = None if app_button is None else open_app(bot, app_button, app_path)
    await bot.send_message(
        chat_id=Omitted() if context.chat_id is None else context.chat_id,
        text=notice,
        notify=False,
        attachments=None if keyboard is None else keyboard_attachments(keyboard),
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


def app_payload(path: str) -> str:
    return encode_payload(json.dumps({"path": path}, separators=(",", ":")))


def open_app(
    bot: Bot,
    text: str,
    path: str | None = None,
) -> list[list[OpenAppButton]] | None:
    web_app = web_app_name(bot)
    if web_app is None:
        return None
    payload = Omitted() if path is None else app_payload(path)
    return [[OpenAppButton(text=text, web_app=web_app, payload=payload)]]


def app_link(bot: Bot, text: str, path: str) -> list[list[LinkButton]] | None:
    if web_app_name(bot) is None:
        return None
    url = create_startapp_link(bot, app_payload(path))
    return [[LinkButton(text=text, url=url)]]


EMERGENCY = Const("🚨 Авария")


class VotePayload(Payload, prefix="vote"):
    poll_id: int
    option_id: int
