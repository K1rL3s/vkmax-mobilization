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

        attachments = None if keyboard is None else _keyboard(keyboard)

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
            with _undelivered():
                async with (
                    BOT_RATE_LIMIT,
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

    async def edit_message(
        self,
        chat_id: MaxChatId,
        mid: str,
        text: str,
        keyboard: Sequence[Sequence[InlineButtons]],
    ) -> bool:
        done = False
        with _undelivered():
            async with BOT_RATE_LIMIT, _chat_rate_limit(chat_id):
                await self._bot.edit_message(
                    message_id=mid,
                    text=text,
                    attachments=_keyboard(keyboard),
                    notify=False,
                )
                done = True
        return done

    async def pin_message(self, chat_id: MaxChatId, mid: str) -> bool:
        done = False
        with _undelivered():
            async with BOT_RATE_LIMIT, _chat_rate_limit(chat_id):
                await self._bot.pin_message(
                    chat_id=chat_id,
                    message_id=mid,
                    notify=False,
                )
                done = True
        return done

    async def delete_message(self, chat_id: MaxChatId, mid: str) -> bool:
        done = False
        with _undelivered():
            async with BOT_RATE_LIMIT, _chat_rate_limit(chat_id):
                await self._bot.delete_message(message_id=mid)
                done = True
        return done


async def is_chat_admin(bot: Bot, chat_id: MaxChatId) -> bool:
    try:
        async with BOT_RATE_LIMIT:
            member = await bot.get_membership(chat_id=chat_id)
    except (MaxBotForbiddenError, MaxBotNotFoundError):
        return False
    return member.is_admin


def _keyboard(
    keyboard: Sequence[Sequence[InlineButtons]],
) -> list[AttachmentsRequests | Attachments]:
    return [InlineKeyboardAttachmentRequest.factory([list(row) for row in keyboard])]
