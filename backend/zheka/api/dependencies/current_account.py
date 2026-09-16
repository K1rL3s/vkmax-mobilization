from datetime import datetime
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends

from zheka.api.dependencies.current_user import CurrentUserDep
from zheka.base import ZhekaType
from zheka.core.errors import NotEnoughRights
from zheka.core.ids import MaxUserId, UserId
from zheka.infra.database.repos.users import UsersRepo


class CurrentAccount(ZhekaType):
    user_id: UserId
    max_user_id: MaxUserId
    name: str
    consent_at: datetime | None


def _full_name(first_name: str, last_name: str | None) -> str:
    return f"{first_name} {last_name}" if last_name else first_name


@inject
async def get_current_account(
    *,
    current_user: CurrentUserDep,
    users_repo: FromDishka[UsersRepo],
) -> CurrentAccount:
    webapp_user = current_user.init_data.user
    user = await users_repo.upsert_by_max_id(
        current_user.max_user_id,
        name=_full_name(webapp_user.first_name, webapp_user.last_name),
        username=webapp_user.username,
    )
    return CurrentAccount(
        user_id=UserId(user.id),
        max_user_id=current_user.max_user_id,
        name=user.name,
        consent_at=user.consent_at,
    )


CurrentAccountDep = Annotated[CurrentAccount, Depends(get_current_account)]


async def require_consent(current_account: CurrentAccountDep) -> CurrentAccount:
    if current_account.consent_at is None:
        raise NotEnoughRights("Нужно согласие на обработку персональных данных")
    return current_account


RequireConsentDep = Annotated[CurrentAccount, Depends(require_consent)]
