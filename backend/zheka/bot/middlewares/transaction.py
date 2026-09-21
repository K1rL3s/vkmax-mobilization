from typing import Any

from dishka import AsyncContainer
from maxo.integrations.dishka import CONTAINER_NAME
from maxo.routing.ctx import Ctx
from maxo.routing.interfaces.middleware import BaseMiddleware, NextMiddleware
from maxo.routing.signals.update import MaxoUpdate
from sqlalchemy.ext.asyncio import AsyncSession

from zheka.broker.publisher import TaskPublisher


class TransactionMiddleware(BaseMiddleware[MaxoUpdate[Any]]):
    __slots__ = ()

    async def __call__(
        self, update: MaxoUpdate[Any], ctx: Ctx, next: NextMiddleware[MaxoUpdate[Any]]
    ) -> Any:
        container: AsyncContainer = ctx[CONTAINER_NAME]
        session = await container.get(AsyncSession)
        try:
            result = await next(ctx)
        except Exception:
            await session.rollback()
            raise

        await session.commit()
        publisher = await container.get(TaskPublisher)
        await publisher.flush()
        return result
