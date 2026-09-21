from dishka import FromDishka
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
from zheka.core.services.orgs import OrgsService

router = APIRouter(tags=["Организации"], route_class=DishkaRoute)


@router.post("/orgs/lookup", summary="Найти УК по ИНН или лицензии")
async def lookup_org(
    current_account: RequireConsentDep,  # noqa: ARG001
    orgs_service: FromDishka[OrgsService],
    body: OrgLookupRequest,
) -> OrgLookupResponse:
    return OrgLookupResponse.of(await orgs_service.lookup(body.inn, body.license_no))


@router.post("/orgs", summary="Зарегистрировать УК")
async def register_org(
    current_account: RequireConsentDep,
    orgs_service: FromDishka[OrgsService],
    body: RegisterOrgRequest,
) -> OrgCard:
    card = await orgs_service.register(
        current_account.user_id,
        body.deeplink_code,
        body.inn,
        body.license_no,
        body.name,
        body.phone,
        body.address,
    )
    return OrgCard.of(card)


@router.post("/org-invites/{code}/activate", summary="Активировать код сотрудника")
async def activate_org_invite(
    code: str, current_account: RequireConsentDep, orgs_service: FromDishka[OrgsService]
) -> OrgMembership:
    membership = await orgs_service.activate_invite(current_account.user_id, code)
    return OrgMembership.of(membership)
