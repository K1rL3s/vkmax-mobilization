from typing import Any, Final

from dishka import AsyncContainer
from maxo.dialogs.api.internal import FakeUser
from maxo.enums import ChatType
from maxo.integrations.dishka import CONTAINER_NAME
from maxo.routing.ctx import Ctx
from maxo.routing.interfaces.middleware import BaseMiddleware, NextMiddleware
from maxo.routing.middlewares.update_context import UPDATE_CONTEXT_KEY
from maxo.routing.signals.update import MaxoUpdate
from maxo.types.update_context import UpdateContext

from zheka.core.ids import MaxChatId, MaxUserId
from zheka.infra.database.repos.users import UsersRepo

USER_KEY: Final = "user"


class UserMiddleware(BaseMiddleware[MaxoUpdate[Any]]):
    # inner и после TransactionMiddleware: DishkaMiddleware регистрируется
    # позже, уже из setup_dishka, поэтому outer-мидлварь отсюда оказалась бы
    # снаружи контейнера, а апсерт - снаружи транзакции, которая его коммитит
    __slots__ = ()

    async def __call__(
        self,
        update: MaxoUpdate[Any],
        ctx: Ctx,
        next: NextMiddleware[MaxoUpdate[Any]],
    ) -> Any:
        context: UpdateContext | None = ctx.get(UPDATE_CONTEXT_KEY)
        if context is None or context.user is None:
            return await next(ctx)

        container: AsyncContainer = ctx[CONTAINER_NAME]
        users_repo = await container.get(UsersRepo)
        max_user = context.user

        if isinstance(max_user, FakeUser):
            # окно, которое открыла задача: FakeUser собран из одних id, имя в
            # нем пустое, и апсерт затер бы им настоящее
            user = await users_repo.get_by_max_id(MaxUserId(max_user.id))
        else:
            user = await users_repo.upsert_by_max_id(
                MaxUserId(max_user.id),
                max_user.fullname,
                max_user.username,
                private_chat_id(context),
            )

        if user is not None:
            ctx[USER_KEY] = user
        return await next(ctx)


def private_chat_id(context: UpdateContext) -> MaxChatId | None:
    # у сообщения из чата дома chat_id чужой, и записывать его как личный
    # нельзя: по нему задача откроет окно всему дому
    if context.chat_type is not ChatType.DIALOG or context.chat_id is None:
        return None
    return MaxChatId(context.chat_id)
