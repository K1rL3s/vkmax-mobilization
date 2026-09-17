from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import AdminOrgDep, CurrentOrgDep
from zheka.api.schemas.base import OkResponse
from zheka.api.schemas.orgs import (
    CreateOrgInviteRequest,
    OrgCard,
    OrgInviteItem,
    OrgMemberItem,
    OrgSettingsResponse,
    UpdateOrgSettingsRequest,
)
from zheka.core.ids import UserId

router = APIRouter(tags=["Админка: организация"], route_class=DishkaRoute)


@router.get("/admin/org", summary="Карточка организации")
async def get_org(current_org: AdminOrgDep) -> OrgCard:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/org/settings", summary="Настройки организации")
async def get_org_settings(current_org: CurrentOrgDep) -> OrgSettingsResponse:
    raise NotImplementedError("ещё не реализовано")


@router.put("/admin/org/settings", summary="Изменить настройки организации")
async def update_org_settings(
    current_org: AdminOrgDep,
    body: UpdateOrgSettingsRequest,
) -> OrgSettingsResponse:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/org/members", summary="Сотрудники организации")
async def list_org_members(current_org: AdminOrgDep) -> list[OrgMemberItem]:
    raise NotImplementedError("ещё не реализовано")


@router.delete("/admin/org/members/{user_id}", summary="Исключить сотрудника")
async def remove_org_member(
    user_id: UserId,
    current_org: AdminOrgDep,
) -> OkResponse:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/org/invites", summary="Приглашения сотрудников")
async def list_org_invites(current_org: AdminOrgDep) -> list[OrgInviteItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post("/admin/org/invites", summary="Создать приглашение сотрудника")
async def create_org_invite(
    current_org: AdminOrgDep,
    body: CreateOrgInviteRequest,
) -> OrgInviteItem:
    raise NotImplementedError("ещё не реализовано")


@router.delete("/admin/org/invites/{code}", summary="Отозвать приглашение")
async def revoke_org_invite(
    code: str,
    current_org: AdminOrgDep,
) -> OkResponse:
    raise NotImplementedError("ещё не реализовано")
