from typing import Any, Final

from dishka import AsyncContainer
from maxo.dialogs import DialogManager
from maxo.dialogs.api.internal import FakeUser
from maxo.enums import ChatType
from maxo.integrations.dishka import CONTAINER_NAME
from maxo.routing.ctx import Ctx
from maxo.routing.interfaces.middleware import BaseMiddleware, NextMiddleware
from maxo.routing.middlewares.update_context import UPDATE_CONTEXT_KEY
from maxo.routing.signals.update import MaxoUpdate
from maxo.types.update_context import UpdateContext

from zheka.core.ids import MaxChatId, MaxUserId, UserId
from zheka.core.models import User
from zheka.infra.database.repos.users import UsersRepo

USER_KEY: Final = "user"


class UserMiddleware(BaseMiddleware[MaxoUpdate[Any]]):
    __slots__ = ()

    async def __call__(
        self,
        update: MaxoUpdate[Any],
        ctx: Ctx,
        next: NextMiddleware[MaxoUpdate[Any]],
    ) -> Any:
        context: UpdateContext = ctx[UPDATE_CONTEXT_KEY]
        if context.user is None:
            return await next(ctx)

        container: AsyncContainer = ctx[CONTAINER_NAME]
        users_repo = await container.get(UsersRepo)
        max_user = context.user

        if isinstance(max_user, FakeUser) or context.chat_type is not ChatType.DIALOG:
            user = await users_repo.get_by_max_id(MaxUserId(max_user.id))
        else:
            user = await users_repo.upsert_by_max_id(
                MaxUserId(max_user.id),
                max_user.fullname,
                max_user.username,
                None if context.chat_id is None else MaxChatId(context.chat_id),
            )

        if user is not None:
            ctx[USER_KEY] = user
        return await next(ctx)


def dialog_user_id(dialog_manager: DialogManager) -> UserId:
    user: User = dialog_manager.middleware_data[USER_KEY]
    return user.id
