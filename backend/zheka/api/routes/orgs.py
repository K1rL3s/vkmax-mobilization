from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import RequireConsentDep
from zheka.api.schemas.orgs import (
    OrgCard,
    OrgLookupRequest,
    OrgLookupResponse,
    OrgMembership,
    RegisterOrgRequest,
)

router = APIRouter(tags=["Организации"], route_class=DishkaRoute)


@router.post("/orgs/lookup", summary="Найти УК по ИНН или лицензии")
async def lookup_org(
    current_account: RequireConsentDep,
    body: OrgLookupRequest,
) -> OrgLookupResponse:
    raise NotImplementedError("ещё не реализовано")


@router.post("/orgs", summary="Зарегистрировать УК")
async def register_org(
    current_account: RequireConsentDep,
    body: RegisterOrgRequest,
) -> OrgCard:
    raise NotImplementedError("ещё не реализовано")


@router.post("/org-invites/{code}/activate", summary="Активировать код сотрудника")
async def activate_org_invite(
    code: str,
    current_account: RequireConsentDep,
) -> OrgMembership:
    raise NotImplementedError("ещё не реализовано")
