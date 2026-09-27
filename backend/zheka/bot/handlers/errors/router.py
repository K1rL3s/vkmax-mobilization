import logging
from contextlib import suppress
from typing import Any

from maxo import Router
from maxo.dialogs import DialogManager
from maxo.dialogs.api.exceptions import (
    InvalidStackIdError,
    OutdatedIntent,
    UnknownIntent,
)
from maxo.enums import ChatType
from maxo.routing.filters import ExceptionTypeFilter
from maxo.routing.middlewares.update_context import UPDATE_CONTEXT_KEY
from maxo.types import BotStarted, ErrorEvent, MessageCallback, MessageCreated
from maxo.types.update_context import UpdateContext

from zheka.bot.cards import ask_in_default_stack
from zheka.bot.states import Menu
from zheka.core.errors import ZhekaError

logger = logging.getLogger(__name__)

STALE_WINDOW = "🔄 Это окно устарело, открываю меню заново"
UNEXPECTED = "⚠️ Что-то пошло не так, попробуйте еще раз"

router = Router(name=__name__)


@router.exception(
    ExceptionTypeFilter(UnknownIntent, OutdatedIntent, InvalidStackIdError),
)
async def stale_window_handler(
    event: ErrorEvent[Any, Any],
    dialog_manager: DialogManager,
) -> None:
    await _notify(event, STALE_WINDOW)
    await _restart_menu(event, dialog_manager)


@router.exception(ExceptionTypeFilter(ZhekaError))
async def domain_error_handler(event: ErrorEvent[ZhekaError, Any]) -> None:
    await _notify(event, str(event.exception))


@router.exception()
async def unexpected_error_handler(
    event: ErrorEvent[Any, Any],
    dialog_manager: DialogManager,
) -> None:
    logger.error("Необработанная ошибка в боте", exc_info=event.exception)
    with suppress(Exception):
        await _notify(event, UNEXPECTED)
        await _restart_menu(event, dialog_manager)


async def _notify(event: ErrorEvent[Any, Any], text: str) -> None:
    update = event.update.update
    if isinstance(update, MessageCallback):
        await update.callback_answer(notification=text)
    elif isinstance(update, MessageCreated):
        await update.reply_text(text, notify=False)
    elif isinstance(update, BotStarted):
        await update.send_message(text=text, notify=False)


async def _restart_menu(
    event: ErrorEvent[Any, Any],
    dialog_manager: DialogManager,
) -> None:
    context: UpdateContext = dialog_manager.middleware_data[UPDATE_CONTEXT_KEY]
    if context.chat_type is ChatType.DIALOG and isinstance(
        event.update.update,
        MessageCallback | MessageCreated | BotStarted,
    ):
        await ask_in_default_stack(dialog_manager, Menu.main, None)
