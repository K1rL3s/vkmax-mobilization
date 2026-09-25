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
    consent_at: datetime | None


@inject
async def get_current_account(
    *,
    current_user: CurrentUserDep,
    users_repo: FromDishka[UsersRepo],
) -> CurrentAccount:
    webapp_user = current_user.user
    user = await users_repo.upsert_by_max_id(
        MaxUserId(webapp_user.id),
        name=(
            f"{webapp_user.first_name} {webapp_user.last_name}"
            if webapp_user.last_name
            else webapp_user.first_name
        ),
        username=webapp_user.username,
    )
    return CurrentAccount(user_id=user.id, consent_at=user.consent_at)


CurrentAccountDep = Annotated[CurrentAccount, Depends(get_current_account)]


async def require_consent(current_account: CurrentAccountDep) -> CurrentAccount:
    if current_account.consent_at is None:
        raise NotEnoughRights("Нужно согласие на обработку персональных данных")
    return current_account


RequireConsentDep = Annotated[CurrentAccount, Depends(require_consent)]
