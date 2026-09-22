from collections.abc import Sequence
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, Header

from zheka.api.dependencies.current_account import CurrentAccountDep
from zheka.base import ZhekaType
from zheka.core.enums import OrgRole
from zheka.core.errors import NotEnoughRights
from zheka.core.ids import OrgId, UserId
from zheka.core.roles import can_manage_houses, is_staff
from zheka.infra.database.models import OrgMember
from zheka.infra.database.repos.orgs import OrgsRepo


class CurrentOrg(ZhekaType):
    org_id: OrgId
    user_id: UserId
    role: OrgRole


def resolve_org(
    memberships: Sequence[OrgMember],
    user_id: UserId,
    org_id_header: OrgId | None,
) -> CurrentOrg:
    if not memberships:
        raise NotEnoughRights("Вы не сотрудник ни одной организации")
    member: OrgMember
    if org_id_header is None:
        if len(memberships) > 1:
            raise NotEnoughRights(
                "Укажите X-Org-Id: вы сотрудник нескольких организаций",
            )
        member = memberships[0]
    else:
        found = next((m for m in memberships if m.org_id == org_id_header), None)
        if found is None:
            raise NotEnoughRights("Нет доступа к этой организации")
        member = found
    if not is_staff(member.role):
        raise NotEnoughRights("Исполнитель работает только через бота")
    return CurrentOrg(org_id=OrgId(member.org_id), user_id=user_id, role=member.role)


@inject
async def get_current_org(
    *,
    current_account: CurrentAccountDep,
    orgs_repo: FromDishka[OrgsRepo],
    org_id_header: Annotated[OrgId | None, Header(alias="X-Org-Id")] = None,
) -> CurrentOrg:
    memberships = await orgs_repo.list_for_user(current_account.user_id)
    return resolve_org(memberships, current_account.user_id, org_id_header)


CurrentOrgDep = Annotated[CurrentOrg, Depends(get_current_org)]


async def require_admin_org(current_org: CurrentOrgDep) -> CurrentOrg:
    if not can_manage_houses(current_org.role):
        raise NotEnoughRights("Нужны права администратора организации")
    return current_org


AdminOrgDep = Annotated[CurrentOrg, Depends(require_admin_org)]
