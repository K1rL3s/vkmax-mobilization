from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter
from maxo import Bot
from maxo.utils.deeplink import create_start_link

from zheka.api.dependencies import AdminOrgDep
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.api.schemas.flats import RejectVerificationRequest, VerificationRequestItem
from zheka.api.schemas.houses import (
    AdminHouseCard,
    AdminHouseListItem,
    BindingCodeResponse,
    BlockResidentRequest,
    EntranceQr,
    HouseResidentItem,
    RevokeVerificationRequest,
    SetChairmanRequest,
)
from zheka.core.deeplinks import entrance_qr_payload, house_payload
from zheka.core.enums import VerificationStatus
from zheka.core.ids import HouseId, ResidentId, VerificationRequestId
from zheka.core.services.flats import FlatsService
from zheka.core.services.houses import HousesService
from zheka.core.services.moderation import ModerationService

router = APIRouter(tags=["Админка: дома"], route_class=DishkaRoute)


@router.get("/admin/houses", summary="Дома организации")
async def list_org_houses(
    current_org: AdminOrgDep,
    houses_service: FromDishka[HousesService],
    q: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[AdminHouseListItem]:
    rows, total = await houses_service.org_houses(current_org.org_id, q, limit, offset)
    return Page(items=[AdminHouseListItem.of(row) for row in rows], total=total)


@router.get("/admin/houses/{house_id}", summary="Карточка дома в админке")
async def get_admin_house_card(
    house_id: HouseId,
    current_org: AdminOrgDep,
    houses_service: FromDishka[HousesService],
    bot: FromDishka[Bot],
) -> AdminHouseCard:
    card = await houses_service.admin_card(current_org.org_id, house_id)
    entrance_qrs = [
        EntranceQr(
            entrance=entrance,
            code=entrance_qr_payload(house_id, entrance),
            deeplink=create_start_link(bot, entrance_qr_payload(house_id, entrance)),
        )
        for entrance in range(1, card.house.entrances + 1)
    ]
    return AdminHouseCard.of(card, entrance_qrs)


@router.post(
    "/admin/houses/{house_id}/binding-code",
    summary="Перевыпустить код привязки чата",
)
async def rotate_house_binding_code(
    house_id: HouseId,
    current_org: AdminOrgDep,
    houses_service: FromDishka[HousesService],
    bot: FromDishka[Bot],
) -> BindingCodeResponse:
    house = await houses_service.rotate_binding_code(current_org.org_id, house_id)
    return BindingCodeResponse(
        house_id=house_id,
        code=house.chat_binding_code,
        deeplink=create_start_link(bot, house_payload(house_id)),
    )


@router.get("/admin/houses/{house_id}/residents", summary="Жители дома")
async def list_house_residents(
    house_id: HouseId,
    current_org: AdminOrgDep,
    houses_service: FromDishka[HousesService],
    q: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[HouseResidentItem]:
    residents, total = await houses_service.house_residents(
        current_org.org_id,
        house_id,
        q,
        limit,
        offset,
    )
    return Page(items=[HouseResidentItem.of(view) for view in residents], total=total)


@router.post("/admin/residents/{resident_id}/block", summary="Заблокировать жителя")
async def block_resident(
    resident_id: ResidentId,
    current_org: AdminOrgDep,
    moderation_service: FromDishka[ModerationService],
    body: BlockResidentRequest,
) -> HouseResidentItem:
    view = await moderation_service.block(
        current_org.org_id,
        resident_id,
        body.reason,
        current_org.user_id,
    )
    return HouseResidentItem.of(view)


@router.post("/admin/residents/{resident_id}/unblock", summary="Разблокировать жителя")
async def unblock_resident(
    resident_id: ResidentId,
    current_org: AdminOrgDep,
    moderation_service: FromDishka[ModerationService],
) -> HouseResidentItem:
    view = await moderation_service.unblock(
        current_org.org_id,
        resident_id,
        current_org.user_id,
    )
    return HouseResidentItem.of(view)


@router.post(
    "/admin/residents/{resident_id}/revoke-verification",
    summary="Отозвать подтверждение квартиры",
)
async def revoke_flat_verification(
    resident_id: ResidentId,
    current_org: AdminOrgDep,
    moderation_service: FromDishka[ModerationService],
    body: RevokeVerificationRequest,
) -> HouseResidentItem:
    view = await moderation_service.revoke_verification(
        current_org.org_id,
        resident_id,
        body.reason,
        current_org.user_id,
    )
    return HouseResidentItem.of(view)


@router.post(
    "/admin/residents/{resident_id}/chairman",
    summary="Назначить председателя",
)
async def set_chairman(
    resident_id: ResidentId,
    current_org: AdminOrgDep,
    moderation_service: FromDishka[ModerationService],
    body: SetChairmanRequest,
) -> HouseResidentItem:
    view = await moderation_service.set_chairman(
        current_org.org_id,
        resident_id,
        body.is_chairman,
    )
    return HouseResidentItem.of(view)


@router.get("/admin/verification-requests", summary="Запросы подтверждения квартир")
async def list_verification_requests(
    current_org: AdminOrgDep,
    flats_service: FromDishka[FlatsService],
    status: VerificationStatus | None = None,
    house_id: HouseId | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[VerificationRequestItem]:
    views, total = await flats_service.verification_requests(
        current_org.org_id,
        status,
        house_id,
        limit,
        offset,
    )
    return Page(items=[VerificationRequestItem.of(view) for view in views], total=total)


@router.post(
    "/admin/verification-requests/{verification_id}/approve",
    summary="Подтвердить квартиру жителю",
)
async def approve_verification_request(
    verification_id: VerificationRequestId,
    current_org: AdminOrgDep,
    flats_service: FromDishka[FlatsService],
) -> VerificationRequestItem:
    view = await flats_service.approve_verification(
        current_org.org_id,
        verification_id,
        current_org.user_id,
    )
    return VerificationRequestItem.of(view)


@router.post(
    "/admin/verification-requests/{verification_id}/reject",
    summary="Отклонить запрос подтверждения",
)
async def reject_verification_request(
    verification_id: VerificationRequestId,
    current_org: AdminOrgDep,
    flats_service: FromDishka[FlatsService],
    body: RejectVerificationRequest,
) -> VerificationRequestItem:
    view = await flats_service.reject_verification(
        current_org.org_id,
        verification_id,
        current_org.user_id,
        body.reason,
    )
    return VerificationRequestItem.of(view)
