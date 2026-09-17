from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import AdminOrgDep
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.api.schemas.flats import (
    RejectVerificationRequest,
    VerificationRequestItem,
)
from zheka.api.schemas.houses import (
    AdminHouseCard,
    AdminHouseListItem,
    BindingCodeResponse,
    BlockResidentRequest,
    HouseResidentItem,
    RevokeVerificationRequest,
    SetChairmanRequest,
)
from zheka.core.enums import VerificationStatus
from zheka.core.ids import HouseId, ResidentId, VerificationRequestId

router = APIRouter(tags=["Админка: дома"], route_class=DishkaRoute)


@router.get("/admin/houses", summary="Дома организации")
async def list_org_houses(
    current_org: AdminOrgDep,
    q: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[AdminHouseListItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/houses/{house_id}", summary="Карточка дома в админке")
async def get_admin_house_card(
    house_id: HouseId,
    current_org: AdminOrgDep,
) -> AdminHouseCard:
    raise NotImplementedError("ещё не реализовано")


@router.post(
    "/admin/houses/{house_id}/binding-code",
    summary="Перевыпустить код привязки чата",
)
async def rotate_house_binding_code(
    house_id: HouseId,
    current_org: AdminOrgDep,
) -> BindingCodeResponse:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/houses/{house_id}/residents", summary="Жители дома")
async def list_house_residents(
    house_id: HouseId,
    current_org: AdminOrgDep,
    q: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[HouseResidentItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post("/admin/residents/{resident_id}/block", summary="Заблокировать жителя")
async def block_resident(
    resident_id: ResidentId,
    current_org: AdminOrgDep,
    body: BlockResidentRequest,
) -> HouseResidentItem:
    raise NotImplementedError("ещё не реализовано")


@router.post("/admin/residents/{resident_id}/unblock", summary="Разблокировать жителя")
async def unblock_resident(
    resident_id: ResidentId,
    current_org: AdminOrgDep,
) -> HouseResidentItem:
    raise NotImplementedError("ещё не реализовано")


@router.post(
    "/admin/residents/{resident_id}/revoke-verification",
    summary="Отозвать подтверждение квартиры",
)
async def revoke_flat_verification(
    resident_id: ResidentId,
    current_org: AdminOrgDep,
    body: RevokeVerificationRequest,
) -> HouseResidentItem:
    raise NotImplementedError("ещё не реализовано")


@router.post(
    "/admin/residents/{resident_id}/chairman", summary="Назначить председателя"
)
async def set_chairman(
    resident_id: ResidentId,
    current_org: AdminOrgDep,
    body: SetChairmanRequest,
) -> HouseResidentItem:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/verification-requests", summary="Запросы подтверждения квартир")
async def list_verification_requests(
    current_org: AdminOrgDep,
    status: VerificationStatus | None = None,
    house_id: HouseId | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[VerificationRequestItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post(
    "/admin/verification-requests/{verification_id}/approve",
    summary="Подтвердить квартиру жителю",
)
async def approve_verification_request(
    verification_id: VerificationRequestId,
    current_org: AdminOrgDep,
) -> VerificationRequestItem:
    raise NotImplementedError("ещё не реализовано")


@router.post(
    "/admin/verification-requests/{verification_id}/reject",
    summary="Отклонить запрос подтверждения",
)
async def reject_verification_request(
    verification_id: VerificationRequestId,
    current_org: AdminOrgDep,
    body: RejectVerificationRequest,
) -> VerificationRequestItem:
    raise NotImplementedError("ещё не реализовано")
