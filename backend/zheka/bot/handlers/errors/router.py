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
from maxo.types import ErrorEvent, MessageCallback, MessageCreated

from zheka.bot.states import Menu
from zheka.core.errors import ZhekaError

logger = logging.getLogger(__name__)

STALE_WINDOW = "Это окно устарело, открываю меню заново"

router = Router(name=__name__)


# роутер ошибок живет снаружи private_router: событие ошибки - это другой
# обсервер, а под фильтром лички в групповом чате все равно ничего не бежит.
# Ни одного сервиса и ни одной записи: maxo вешает ErrorMiddleware первой
# outer-мидлварью dp.update, то есть снаружи DishkaMiddleware и снаружи
# TransactionMiddleware. К этому моменту сессия откачена, а запросный
# контейнер закрыт, и @inject резолвил бы из закрытого
@router.exception(
    ExceptionTypeFilter(UnknownIntent, OutdatedIntent, InvalidStackIdError),
)
async def stale_window_handler(
    event: ErrorEvent[Any, Any],
    dialog_manager: DialogManager,
) -> None:
    # нажатие на окно, чей стек уже не существует: перезапуск на середине
    # потока, тридцатидневный TTL состояния или более свежий RESET_STACK
    await _notify(event, STALE_WINDOW)
    await dialog_manager.start(Menu.main, mode=StartMode.RESET_STACK)


@router.exception(ExceptionTypeFilter(ZhekaError))
async def domain_error_handler(event: ErrorEvent[ZhekaError, Any]) -> None:
    await _notify(event, str(event.exception))


@router.exception()
async def unexpected_error_handler(event: ErrorEvent[Any, Any]) -> None:
    logger.error(
        "Необработанная ошибка в боте",
        exc_info=event.exception,
    )
    raise event.exception


async def _notify(event: ErrorEvent[Any, Any], text: str) -> None:
    # сообщением, а не только колбэком: обработчик, вернувший None, для
    # ErrorMiddleware разобран, и ошибка при вводе текста пропала бы совсем
    update = event.update.update
    if isinstance(update, MessageCallback):
        await update.callback_answer(notification=text)
    elif isinstance(update, MessageCreated):
        await update.answer_text(text, notify=False)
