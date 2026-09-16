from typing import Any

from maxo import Ctx
from maxo.routing.interfaces import BaseMiddleware, NextMiddleware
from maxo.routing.middlewares.update_context import EVENT_FROM_USER_KEY
from maxo.types import MessageCallback, MessageCreated


class ThrottlingMiddleware(BaseMiddleware[MessageCreated | MessageCallback]):
    __slots__ = ("_cache",)

    def __init__(self) -> None:
        self._cache: set[int] = set()

    async def __call__(
        self,
        update: MessageCreated | MessageCallback,
        ctx: Ctx,
        next: NextMiddleware[MessageCreated | MessageCallback],
    ) -> Any:
        user = ctx.get(EVENT_FROM_USER_KEY)
        if user is None:
            return await next(ctx)

        if user.id in self._cache:
            return None

        self._cache.add(user.id)
        try:
            return await next(ctx)
        finally:
            self._cache.discard(user.id)
