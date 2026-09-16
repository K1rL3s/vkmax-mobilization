import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from maxo import Bot
from maxo.errors import (
    MaxBotApiError,
    MaxBotForbiddenError,
    MaxBotNetworkError,
    MaxBotNotFoundError,
)
from maxo.types.buttons import InlineButtons
from maxo.types.inline_keyboard_attachment_request import (
    InlineKeyboardAttachmentRequest,
)
from maxo.types.send_message_result import SendMessageResult

from zheka.core.ids import MaxChatId, MaxUserId
from zheka.infra.max.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

BOT_RATE_LIMIT = RateLimiter(max_calls=30, period=1.0)


@lru_cache(maxsize=4096)
def _chat_rate_limit(recipient: int) -> RateLimiter:  # noqa: ARG001
    return RateLimiter(max_calls=2, period=1.0)


class MaxSender:
    __slots__ = ("_bot",)

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

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
