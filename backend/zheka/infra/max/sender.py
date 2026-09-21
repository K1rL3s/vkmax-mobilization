import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache

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
from maxo.omit import Omitted
from maxo.types import Attachments, AttachmentsRequests
from maxo.types.buttons import InlineButtons
from maxo.types.inline_keyboard_attachment_request import (
    InlineKeyboardAttachmentRequest,
)
from maxo.types.send_message_result import SendMessageResult

from zheka.core.ids import MaxChatId, MaxUserId
from zheka.core.models import User
from zheka.infra.max.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

BOT_RATE_LIMIT = RateLimiter(max_calls=30)

# звук окна диалога для ZhekaMessageManager, поднимает его только start_dialog
dialog_notify: ContextVar[bool] = ContextVar("dialog_notify", default=False)


@lru_cache(maxsize=4096)
def _chat_rate_limit(recipient: int) -> RateLimiter:  # noqa: ARG001
    return RateLimiter(max_calls=2)


@contextmanager
def _undelivered() -> Iterator[None]:
    try:
        yield
    except (MaxBotNotFoundError, MaxBotForbiddenError) as error:
        logger.warning("Получатель недоступен, бот остановлен или удалён: %s", error)
    except (MaxBotNetworkError, MaxBotApiError):
        logger.exception("MAX не принял сообщение")


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
    ) -> SendMessageResult | None:
        recipient = chat_id if chat_id is not None else user_id
        if recipient is None:
            raise ValueError("Нужен либо chat_id, либо user_id")

        attachments: list[AttachmentsRequests | Attachments] | None = None
        if keyboard is not None:
            attachments = [
                InlineKeyboardAttachmentRequest.factory([list(row) for row in keyboard])
            ]

        result: SendMessageResult | None = None
        with _undelivered():
            async with BOT_RATE_LIMIT, _chat_rate_limit(recipient):
                result = await self._bot.send_message(
                    text=text,
                    chat_id=Omitted() if chat_id is None else chat_id,
                    user_id=Omitted() if user_id is None else user_id,
                    notify=notify,
                    attachments=attachments,
                )
        return result

    async def start_dialog(
        self,
        state: State,
        user: User,
        *,
        notify: bool,
        data: Data = None,
        stack_id: str | None = None,
        show_mode: ShowMode | None = None,
    ) -> None:
        # RESET_STACK, а не NEW_STACK: тот снова уходит через call_soon и
        # возвращается раньше отправки, от чего здесь и стоит fg()
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
            # fg(), а не bg().start(): тот отдает апдейт в call_soon, и задача
            # закоммитилась бы раньше отправки
            with _undelivered():
                async with (
                    BOT_RATE_LIMIT,
                    # по max_user_id, как и рассылка: ведро на max_chat_id было
                    # бы вторым на тот же чат
                    _chat_rate_limit(user.max_user_id),
                    manager.fg() as dialog_manager,
                ):
                    await dialog_manager.start(
                        state,
                        data=data,
                        mode=StartMode.RESET_STACK,
                        show_mode=show_mode,
                    )
        finally:
            dialog_notify.reset(token)


async def is_chat_admin(bot: Bot, chat_id: MaxChatId) -> bool:
    # 403 и 404 значат, что бота в чате уже нет, а сбой сети или сервера
    # ничего о правах не говорит и поднимается дальше
    try:
        async with BOT_RATE_LIMIT:
            member = await bot.get_membership(chat_id=chat_id)
    except (MaxBotForbiddenError, MaxBotNotFoundError):
        return False
    return member.is_admin
