import secrets
from collections.abc import Awaitable, Callable

from zheka.core.errors import InvalidState

# token_urlsafe(8) дает 11 символов, а code - это String(16).
# Столкновение кодов почти невероятно, но повторная генерация дешевле,
# чем 500 на уникальном индексе
INVITE_CODE_ATTEMPTS = 5


async def issue_invite[InviteT](
    create: Callable[[str], Awaitable[InviteT | None]],
) -> InviteT:
    # create отвечает None на занятый код, а не исключением: IntegrityError
    # увел бы в откат всю транзакцию вызывающего
    for _ in range(INVITE_CODE_ATTEMPTS):
        invite = await create(secrets.token_urlsafe(8))
        if invite is not None:
            return invite
    raise InvalidState("Не удалось выдать код, попробуйте еще раз")
