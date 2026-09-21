import logging
from collections.abc import Sequence
from contextvars import ContextVar
from functools import lru_cache
from typing import Any

from maxo import Bot
from maxo.dialogs import BgManagerFactory, Data, ShowMode, StartMode
from maxo.enums import ChatType
from maxo.errors import (
    MaxBotApiError,
    MaxBotForbiddenError,
    MaxBotNetworkError,
    MaxBotNotFoundError,
)
from maxo.fsm import State
from maxo.types.buttons import InlineButtons
from maxo.types.inline_keyboard_attachment_request import (
    InlineKeyboardAttachmentRequest,
)
from maxo.types.send_message_result import SendMessageResult

from zheka.core.ids import MaxChatId, MaxUserId
from zheka.core.models import User
from zheka.infra.max.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

BOT_RATE_LIMIT = RateLimiter(max_calls=30, period=1.0)

# звук окна диалога: ZhekaMessageManager читает его на каждой отправке.
# Дефолт продуктовый - молча, поднимает флаг только start_dialog
dialog_notify: ContextVar[bool] = ContextVar("dialog_notify", default=False)


@lru_cache(maxsize=4096)
def _chat_rate_limit(recipient: int) -> RateLimiter:  # noqa: ARG001
    return RateLimiter(max_calls=2, period=1.0)


class MaxSender:
    __slots__ = ("_bot", "_dialogs")

    def __init__(self, bot: Bot, bg_manager_factory: BgManagerFactory) -> None:
        self._bot = bot
        self._dialogs = bg_manager_factory

    async def send_message(
        self,
        text: str,
        *,
        chat_id: MaxChatId | None = None,
        user_id: MaxUserId | None = None,
        notify: bool = False,
        keyboard: Sequence[Sequence[InlineButtons]] | None = None,
        **kwargs: Any,
    ) -> SendMessageResult | None:
        recipient = chat_id if chat_id is not None else user_id
        if recipient is None:
            raise ValueError("Нужен либо chat_id, либо user_id")

        if keyboard is not None:
            kwargs["attachments"] = [
                InlineKeyboardAttachmentRequest.factory(
                    [list(row) for row in keyboard],
                ),
            ]

        async with BOT_RATE_LIMIT, _chat_rate_limit(recipient):
            return await self._send(
                text=text,
                chat_id=chat_id,
                user_id=user_id,
                notify=notify,
                **kwargs,
            )

    async def _send(self, **kwargs: Any) -> SendMessageResult | None:
        clean = {key: value for key, value in kwargs.items() if value is not None}
        try:
            return await self._bot.send_message(**clean)
        except (MaxBotNotFoundError, MaxBotForbiddenError) as error:
            logger.warning(
                "Получатель недоступен, бот остановлен или удалён: %s", error
            )
        except MaxBotNetworkError:
            logger.exception("Сеть не дала отправить сообщение")
        except MaxBotApiError:
            logger.exception("MAX отказал в отправке сообщения")
        return None

    async def start_dialog(
        self,
        state: State,
        user: User,
        *,
        notify: bool,
        data: Data = None,
        mode: StartMode = StartMode.RESET_STACK,
        stack_id: str | None = None,
        show_mode: ShowMode | None = None,
    ) -> None:
        # единственный способ задачи открыть или заменить окно: потолки MAX
        # остаются в одном классе, а notify - явным аргументом.
        # RESET_STACK, а не NEW_STACK: последний внутри менеджера снова уходит
        # через call_soon и возвращается раньше отправки, то есть ровно та
        # беда, от которой тут стоит fg(). Отдельный стек для окна задается
        # своим stack_id, и он остается синхронным
        if user.max_chat_id is None or user.bot_stopped_at is not None:
            logger.info(
                "У пользователя %s нет живого личного чата с ботом, окно не открыто",
                user.id,
            )
            return

        manager = self._dialogs.bg(
            bot=self._bot,
            user_id=user.max_user_id,
            chat_id=user.max_chat_id,
            stack_id=stack_id,
            chat_type=ChatType.DIALOG,
        )
        token = dialog_notify.set(notify)
        try:
            # fg(), а не bg().start(): тот отдает апдейт в call_soon и
            # возвращается сразу, и задача успела бы закоммититься раньше
            # отправки, а ошибка всплыла бы непрочитанной
            async with (
                BOT_RATE_LIMIT,
                # по max_user_id, как и рассылка: у личного диалога два разных
                # id, и ведро на max_chat_id было бы вторым на тот же чат
                _chat_rate_limit(user.max_user_id),
                manager.fg() as dialog_manager,
            ):
                await dialog_manager.start(
                    state,
                    data=data,
                    mode=mode,
                    show_mode=show_mode,
                )
        except (MaxBotNotFoundError, MaxBotForbiddenError) as error:
            logger.warning(
                "Получатель недоступен, бот остановлен или удалён: %s", error
            )
        except MaxBotNetworkError:
            logger.exception("Сеть не дала открыть окно")
        except MaxBotApiError:
            logger.exception("MAX отказал в отправке сообщения")
        finally:
            dialog_notify.reset(token)
