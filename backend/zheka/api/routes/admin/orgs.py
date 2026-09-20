from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter
from maxo import Bot
from maxo.utils.deeplink import create_start_link

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
from zheka.core.deeplinks import org_invite_payload
from zheka.core.ids import UserId
from zheka.core.roles import can_remove_member
from zheka.core.services.orgs import OrgsService

router = APIRouter(tags=["Админка: организация"], route_class=DishkaRoute)


@router.get("/admin/org", summary="Карточка организации")
async def get_org(
    current_org: AdminOrgDep,
    orgs_service: FromDishka[OrgsService],
) -> OrgCard:
    return OrgCard.of(await orgs_service.card(current_org.org_id))


@router.get("/admin/org/settings", summary="Настройки организации")
async def get_org_settings(
    current_org: CurrentOrgDep,
    orgs_service: FromDishka[OrgsService],
) -> OrgSettingsResponse:
    return OrgSettingsResponse.of(await orgs_service.settings(current_org.org_id))


@router.put("/admin/org/settings", summary="Изменить настройки организации")
async def update_org_settings(
    current_org: AdminOrgDep,
    orgs_service: FromDishka[OrgsService],
    body: UpdateOrgSettingsRequest,
) -> OrgSettingsResponse:
    view = await orgs_service.update_settings(
        current_org.org_id,
        body.meter_window_day_from,
        body.meter_window_day_to,
        body.meter_window_always_open,
        body.group_threshold,
        body.group_window_hours,
        body.phone,
        body.reception_note,
    )
    return OrgSettingsResponse.of(view)


@router.get("/admin/org/members", summary="Сотрудники организации")
async def list_org_members(
    current_org: AdminOrgDep,
    orgs_service: FromDishka[OrgsService],
) -> list[OrgMemberItem]:
    members = await orgs_service.members(current_org.org_id)
    return [
        OrgMemberItem.of(
            view,
            can_remove=can_remove_member(current_org.role, view.member.role),
        )
        for view in members
    ]


@router.delete("/admin/org/members/{user_id}", summary="Исключить сотрудника")
async def remove_org_member(
    user_id: UserId,
    current_org: AdminOrgDep,
    orgs_service: FromDishka[OrgsService],
) -> OkResponse:
    await orgs_service.remove_member(current_org.org_id, current_org.role, user_id)
    return OkResponse()


@router.get("/admin/org/invites", summary="Приглашения сотрудников")
async def list_org_invites(
    current_org: AdminOrgDep,
    orgs_service: FromDishka[OrgsService],
    bot: FromDishka[Bot],
) -> list[OrgInviteItem]:
    invites = await orgs_service.invites(current_org.org_id)
    return [
        OrgInviteItem.of(
            invite,
            create_start_link(bot, org_invite_payload(invite.code)),
        )
        for invite in invites
    ]


@router.post("/admin/org/invites", summary="Создать приглашение сотрудника")
async def create_org_invite(
    current_org: AdminOrgDep,
    orgs_service: FromDishka[OrgsService],
    bot: FromDishka[Bot],
    body: CreateOrgInviteRequest,
) -> OrgInviteItem:
    invite = await orgs_service.create_invite(
        current_org.org_id,
        current_org.user_id,
        current_org.role,
        body.role,
        body.expires_in_hours,
        body.max_activations,
    )
    return OrgInviteItem.of(
        invite,
        create_start_link(bot, org_invite_payload(invite.code)),
    )


@router.delete("/admin/org/invites/{code}", summary="Отозвать приглашение")
async def revoke_org_invite(
    code: str,
    current_org: AdminOrgDep,
    orgs_service: FromDishka[OrgsService],
) -> OkResponse:
    await orgs_service.revoke_invite(current_org.org_id, code)
    return OkResponse()
