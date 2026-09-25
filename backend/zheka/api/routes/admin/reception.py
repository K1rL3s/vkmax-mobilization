from datetime import date

from dishka import FromDishka
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
from zheka.core.services.access import (
    AccessRequestDraft,
    AccessService,
    AccessSlotDraft,
)
from zheka.core.services.reception import ReceptionService, ReceptionWindowDraft

router = APIRouter(tags=["Админка: прием и доступ"], route_class=DishkaRoute)


@router.get("/admin/reception/windows", summary="Часы приема организации")
async def list_reception_windows(
    current_org: AdminOrgDep,
    reception_service: FromDishka[ReceptionService],
) -> list[ReceptionWindowItem]:
    windows = await reception_service.windows(current_org.org_id)
    return [ReceptionWindowItem.model_validate(window) for window in windows]


@router.put(
    "/admin/reception/windows",
    summary="Задать часы приема",
    description=(
        "Заменяет всю сетку целиком. Несколько окон в один день - это "
        "обеденный перерыв, пустой список - прием не ведется. capacity - "
        "сколько жителей принимают в один слот"
    ),
)
async def set_reception_windows(
    current_org: AdminOrgDep,
    body: SetReceptionWindowsRequest,
    reception_service: FromDishka[ReceptionService],
) -> list[ReceptionWindowItem]:
    windows = await reception_service.set_windows(
        current_org.org_id,
        [ReceptionWindowDraft(**window.model_dump()) for window in body.windows],
    )
    return [ReceptionWindowItem.model_validate(window) for window in windows]


@router.get(
    "/admin/appointments",
    summary="Записи на прием",
    description="Без даты - на сегодня",
)
async def list_org_appointments(
    current_org: CurrentOrgDep,
    reception_service: FromDishka[ReceptionService],
    on_date: date | None = None,
    house_id: HouseId | None = None,
) -> list[AppointmentItem]:
    rows = await reception_service.today(current_org.org_id, on_date, house_id)
    return [AppointmentItem.of(row) for row in rows]


@router.post(
    "/admin/access-requests",
    summary="Собрать доступ в квартиры",
    description=(
        "Ячейку получают только квартиры с подтвержденным жителем, "
        "остальные возвращаются в flats_without_residents"
    ),
)
async def create_access_request(
    current_org: CurrentOrgDep,
    body: CreateAccessRequestRequest,
    access_service: FromDishka[AccessService],
) -> AccessRequestGrid:
    grid = await access_service.create(
        current_org.org_id,
        current_org.user_id,
        AccessRequestDraft(
            **body.model_dump(exclude={"slots"}),
            slots=[AccessSlotDraft(**slot.model_dump()) for slot in body.slots],
        ),
    )
    return AccessRequestGrid.of(grid)


@router.get("/admin/access-requests", summary="Запросы доступа организации")
async def list_org_access_requests(
    current_org: CurrentOrgDep,
    access_service: FromDishka[AccessService],
    house_id: HouseId | None = None,
) -> list[AccessRequestItem]:
    rows = await access_service.list_for_org(current_org.org_id, house_id)
    return [AccessRequestItem.of(row) for row in rows]


@router.get(
    "/admin/access-requests/{access_request_id}",
    summary="Сетка квартир по слотам доступа",
)
async def get_access_request_grid(
    access_request_id: AccessRequestId,
    current_org: CurrentOrgDep,
    access_service: FromDishka[AccessService],
) -> AccessRequestGrid:
    grid = await access_service.grid(current_org.org_id, access_request_id)
    return AccessRequestGrid.of(grid)
