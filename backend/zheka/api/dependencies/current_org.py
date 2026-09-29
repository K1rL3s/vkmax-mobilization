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
from zheka.core.models import User
from zheka.core.services.demo import DEMO_LOCKED
from zheka.infra.database.models import OrgMember
from zheka.infra.database.repos.orgs import OrgsRepo


class CurrentOrg(ZhekaType):
    org_id: OrgId
    user_id: UserId
    role: OrgRole
    is_demo: bool

    def phone_of(self, user: User | None) -> str | None:
        if user is None or (self.is_demo and user.id != self.user_id):
            return None
        return user.phone


def resolve_org(
    memberships: Sequence[OrgMember],
    org_id_header: OrgId | None,
) -> OrgMember:
    if not memberships:
        raise NotEnoughRights("Вы не сотрудник ни одной организации")
    member = next((m for m in memberships if m.org_id == org_id_header), None)
    if org_id_header is None:
        if len(memberships) > 1:
            raise NotEnoughRights(
                "Укажите X-Org-Id: вы сотрудник нескольких организаций",
            )
        member = memberships[0]
    elif member is None:
        raise NotEnoughRights("Нет доступа к этой организации")
    if not member.role.is_staff:
        raise NotEnoughRights("Исполнитель работает только через бота")
    return member


@inject
async def get_current_org(
    *,
    current_account: CurrentAccountDep,
    orgs_repo: FromDishka[OrgsRepo],
    org_id_header: Annotated[OrgId | None, Header(alias="X-Org-Id")] = None,
) -> CurrentOrg:
    memberships = await orgs_repo.list_for_user(current_account.user_id)
    member = resolve_org(memberships, org_id_header)
    org = await orgs_repo.get_existing(member.org_id)
    return CurrentOrg(
        org_id=member.org_id,
        user_id=current_account.user_id,
        role=member.role,
        is_demo=org.is_demo,
    )


CurrentOrgDep = Annotated[CurrentOrg, Depends(get_current_org)]


async def require_admin_org(current_org: CurrentOrgDep) -> CurrentOrg:
    if not current_org.role.can_manage_houses:
        raise NotEnoughRights("Нужны права администратора организации")
    return current_org


AdminOrgDep = Annotated[CurrentOrg, Depends(require_admin_org)]


async def require_live_org(current_org: AdminOrgDep) -> CurrentOrg:
    if current_org.is_demo:
        raise NotEnoughRights(DEMO_LOCKED)
    return current_org


LiveAdminOrgDep = Annotated[CurrentOrg, Depends(require_live_org)]
