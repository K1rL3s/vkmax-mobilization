import logging
import time
from typing import Any

from maxo import Ctx
from maxo.routing.interfaces import BaseMiddleware, NextMiddleware
from maxo.routing.middlewares.update_context import EVENT_FROM_USER_KEY
from maxo.routing.sentinels import REJECTED, UNHANDLED
from maxo.routing.signals import MaxoUpdate

from zheka.logger.context import max_user_id, update_id

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware[MaxoUpdate[Any]]):
    __slots__ = ()

    async def __call__(
        self,
        update: MaxoUpdate[Any],
        ctx: Ctx,
        next: NextMiddleware[MaxoUpdate[Any]],
    ) -> Any:
        update_token = update_id.set(str(update.marker))
        user = ctx.get(EVENT_FROM_USER_KEY)
        user_token = max_user_id.set(getattr(user, "id", None))

        started = time.perf_counter()
        handled = False
        try:
            response = await next(ctx)
            handled = response not in (UNHANDLED, REJECTED)
            return response
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            logger.debug(
                "Апдейт %s %s за %.1f мс",
                update.marker,
                "обработан" if handled else "не обработан",
                elapsed,
            )
            max_user_id.reset(user_token)
            update_id.reset(update_token)
