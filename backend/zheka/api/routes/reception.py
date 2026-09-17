from datetime import date

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

router = APIRouter(tags=["Прием и доступ"], route_class=DishkaRoute)


@router.get("/houses/{house_id}/reception-slots", summary="Свободные слоты приема")
async def list_reception_slots(
    house_id: HouseId,
    residency: ResidencyForHouseDep,
    on_date: date | None = None,
) -> list[ReceptionSlotItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/appointments", summary="Мои записи на прием")
async def list_my_appointments(
    residency: CurrentResidencyDep,
) -> list[AppointmentItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post("/appointments", summary="Записаться на прием")
async def book_appointment(
    residency: CurrentResidencyDep,
    body: BookAppointmentRequest,
) -> AppointmentItem:
    raise NotImplementedError("ещё не реализовано")


@router.delete("/appointments/{appointment_id}", summary="Отменить запись на прием")
async def cancel_appointment(
    appointment_id: AppointmentId,
    current_account: RequireConsentDep,
) -> OkResponse:
    raise NotImplementedError("ещё не реализовано")


@router.get("/access-requests", summary="Запросы доступа в мою квартиру")
async def list_my_access_requests(
    residency: CurrentResidencyDep,
) -> list[AccessRequestItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post(
    "/access-requests/{access_request_id}/slots/{slot_id}",
    summary="Выбрать слот доступа",
)
async def pick_access_slot(
    access_request_id: AccessRequestId,
    slot_id: AccessSlotId,
    current_account: RequireConsentDep,
) -> AccessRequestItem:
    raise NotImplementedError("ещё не реализовано")
