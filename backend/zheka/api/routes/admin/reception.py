from datetime import date

from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import AdminOrgDep, CurrentOrgDep
from zheka.api.schemas.access import (
    AccessRequestGrid,
    AccessRequestItem,
    CreateAccessRequestRequest,
)
from zheka.api.schemas.reception import (
    AppointmentItem,
    ReceptionWindowItem,
    SetReceptionWindowsRequest,
)
from zheka.core.ids import AccessRequestId, HouseId

router = APIRouter(tags=["Админка: прием и доступ"], route_class=DishkaRoute)


@router.get("/admin/reception/windows", summary="Часы приема организации")
async def list_reception_windows(current_org: AdminOrgDep) -> list[ReceptionWindowItem]:
    raise NotImplementedError("ещё не реализовано")


@router.put("/admin/reception/windows", summary="Задать часы приема")
async def set_reception_windows(
    current_org: AdminOrgDep,
    body: SetReceptionWindowsRequest,
) -> list[ReceptionWindowItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/appointments", summary="Записи на прием")
async def list_org_appointments(
    current_org: CurrentOrgDep,
    on_date: date | None = None,
    house_id: HouseId | None = None,
) -> list[AppointmentItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post("/admin/access-requests", summary="Собрать доступ в квартиры")
async def create_access_request(
    current_org: CurrentOrgDep,
    body: CreateAccessRequestRequest,
) -> AccessRequestGrid:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/access-requests", summary="Запросы доступа организации")
async def list_org_access_requests(
    current_org: CurrentOrgDep,
    house_id: HouseId | None = None,
) -> list[AccessRequestItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get(
    "/admin/access-requests/{access_request_id}",
    summary="Сетка квартир по слотам доступа",
)
async def get_access_request_grid(
    access_request_id: AccessRequestId,
    current_org: CurrentOrgDep,
) -> AccessRequestGrid:
    raise NotImplementedError("ещё не реализовано")
