from datetime import datetime, time
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import AppointmentStatus
from zheka.core.ids import AppointmentId, HouseId, OrgId, ReceptionWindowId, RequestId
from zheka.core.services.reception import AppointmentData


class ReceptionSlotItem(BaseSchema):
    starts_at: datetime
    is_free: bool


class AppointmentItem(BaseSchema):
    id: AppointmentId
    created_at: datetime
    org_id: OrgId
    house_id: HouseId
    address: str
    starts_at: datetime
    status: AppointmentStatus
    org_address: str
    org_phone: str
    request_id: RequestId | None = None
    user_name: str | None = None
    flat_number: str | None = None

    @classmethod
    def of(cls, data: AppointmentData) -> Self:
        appointment = data.appointment
        return cls(
            id=appointment.id,
            created_at=appointment.created_at,
            org_id=appointment.org_id,
            house_id=appointment.house_id,
            address=data.address,
            starts_at=appointment.starts_at,
            status=appointment.status,
            org_address=data.org_address,
            org_phone=data.org_phone,
            request_id=appointment.request_id,
            user_name=data.user_name,
            flat_number=data.flat_number,
        )


class BookAppointmentRequest(BaseSchema):
    starts_at: datetime
    request_id: RequestId | None = None


class ReceptionWindowInput(BaseSchema):
    weekday: int = Field(description="День недели, 0 - понедельник, 6 - воскресенье")
    time_from: time
    time_to: time
    slot_minutes: int = Field(description="Длина слота в минутах, от 5 до 240")
    capacity: int = Field(
        default=1,
        description=(
            "Сколько жителей принимают в один слот: столько, сколько "
            "сотрудников ведет прием в этот день"
        ),
    )


class ReceptionWindowItem(ReceptionWindowInput):
    id: ReceptionWindowId


class SetReceptionWindowsRequest(BaseSchema):
    windows: list[ReceptionWindowInput]
