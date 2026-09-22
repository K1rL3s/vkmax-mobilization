import logging
from typing import Any

from maxo import Router
from maxo.dialogs import DialogManager, StartMode
from maxo.dialogs.api.exceptions import (
    InvalidStackIdError,
    OutdatedIntent,
    UnknownIntent,
)
from maxo.routing.filters import ExceptionTypeFilter
from maxo.types import BotStarted, ErrorEvent, MessageCallback, MessageCreated

from zheka.bot.states import Menu
from zheka.core.errors import ZhekaError

logger = logging.getLogger(__name__)

STALE_WINDOW = "🔄 Это окно устарело, открываю меню заново"

router = Router(name=__name__)


@router.exception(
    ExceptionTypeFilter(UnknownIntent, OutdatedIntent, InvalidStackIdError),
)
async def stale_window_handler(
    event: ErrorEvent[Any, Any],
    dialog_manager: DialogManager,
) -> None:
    await _notify(event, STALE_WINDOW)
    await dialog_manager.start(Menu.main, mode=StartMode.RESET_STACK)


@router.exception(ExceptionTypeFilter(ZhekaError))
async def domain_error_handler(event: ErrorEvent[ZhekaError, Any]) -> None:
    await _notify(event, str(event.exception))


@router.exception()
async def unexpected_error_handler(event: ErrorEvent[Any, Any]) -> None:
    logger.error("Необработанная ошибка в боте", exc_info=event.exception)
    raise event.exception


async def _notify(event: ErrorEvent[Any, Any], text: str) -> None:
    update = event.update.update
    if isinstance(update, MessageCallback):
        await update.callback_answer(notification=text)
    elif isinstance(update, MessageCreated):
        await update.reply_text(text, notify=False)
    elif isinstance(update, BotStarted):
        await update.send_message(text=text, notify=False)
