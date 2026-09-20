from datetime import date

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import (
    CurrentResidencyDep,
    RequireConsentDep,
    ResidencyForHouseDep,
)
from zheka.api.schemas.access import AccessRequestItem
from zheka.api.schemas.base import OkResponse
from zheka.api.schemas.reception import (
    AppointmentItem,
    BookAppointmentRequest,
    ReceptionSlotItem,
)
from zheka.core.ids import AccessRequestId, AccessSlotId, AppointmentId, HouseId
from zheka.core.services.access import AccessService
from zheka.core.services.reception import ReceptionService, horizon

router = APIRouter(tags=["Прием и доступ"], route_class=DishkaRoute)


@router.get(
    "/houses/{house_id}/reception-slots",
    summary="Свободные слоты приема",
    description=(
        "Без даты - слоты на две недели вперед, с датой - только на этот "
        "день. Занятый слот приходит с is_free=false, прошедший не приходит "
        "вовсе"
    ),
)
async def list_reception_slots(
    house_id: HouseId,
    residency: ResidencyForHouseDep,  # noqa: ARG001
    reception_service: FromDishka[ReceptionService],
    on_date: date | None = None,
) -> list[ReceptionSlotItem]:
    date_from, date_to = horizon(on_date)
    slots = await reception_service.slots(house_id, date_from, date_to)
    return [ReceptionSlotItem.of(slot) for slot in slots]


@router.get("/appointments", summary="Мои записи на прием")
async def list_my_appointments(
    residency: CurrentResidencyDep,
    reception_service: FromDishka[ReceptionService],
) -> list[AppointmentItem]:
    rows = await reception_service.mine(residency.user_id)
    return [AppointmentItem.of(row) for row in rows]


@router.post(
    "/appointments",
    summary="Записаться на прием",
    description="request_id - заявка жителя по этому дому, чтобы обсудить ее",
)
async def book_appointment(
    residency: CurrentResidencyDep,
    body: BookAppointmentRequest,
    reception_service: FromDishka[ReceptionService],
) -> AppointmentItem:
    booked = await reception_service.book(
        residency.user_id,
        residency.house_id,
        body.starts_at,
        body.request_id,
    )
    return AppointmentItem.of(booked)


@router.delete(
    "/appointments/{appointment_id}",
    summary="Отменить запись на прием",
    description="Отмена освобождает слот для следующего жителя",
)
async def cancel_appointment(
    appointment_id: AppointmentId,
    current_account: RequireConsentDep,
    reception_service: FromDishka[ReceptionService],
) -> OkResponse:
    await reception_service.cancel(appointment_id, current_account.user_id)
    return OkResponse()


@router.get("/access-requests", summary="Запросы доступа в мою квартиру")
async def list_my_access_requests(
    residency: CurrentResidencyDep,
    access_service: FromDishka[AccessService],
) -> list[AccessRequestItem]:
    rows = await access_service.list_for_resident(residency.flat_id)
    return [AccessRequestItem.of(row) for row in rows]


@router.post(
    "/access-requests/{access_request_id}/slots/{slot_id}",
    summary="Выбрать слот доступа",
    description="Выбор можно поменять, пока в окне есть места",
)
async def pick_access_slot(
    access_request_id: AccessRequestId,
    slot_id: AccessSlotId,
    current_account: RequireConsentDep,
    access_service: FromDishka[AccessService],
) -> AccessRequestItem:
    picked = await access_service.pick(
        current_account.user_id,
        access_request_id,
        slot_id,
    )
    return AccessRequestItem.of(picked)
