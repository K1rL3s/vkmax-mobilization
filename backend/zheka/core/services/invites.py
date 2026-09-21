import secrets
from collections.abc import Awaitable, Callable

from zheka.core.errors import InvalidState

INVITE_CODE_ATTEMPTS = 5


async def issue_invite[InviteT](
    create: Callable[[str], Awaitable[InviteT | None]],
) -> InviteT:
    for _ in range(INVITE_CODE_ATTEMPTS):
        invite = await create(secrets.token_urlsafe(8))
        if invite is not None:
            return invite
    raise InvalidState("Не удалось выдать код, попробуйте еще раз")
