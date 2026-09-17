from datetime import datetime, time

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import AppointmentStatus
from zheka.core.ids import AppointmentId, HouseId, OrgId, ReceptionWindowId, RequestId


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


class BookAppointmentRequest(BaseSchema):
    starts_at: datetime
    request_id: RequestId | None = None


class ReceptionWindowInput(BaseSchema):
    weekday: int
    time_from: time
    time_to: time
    slot_minutes: int


class ReceptionWindowItem(ReceptionWindowInput):
    id: ReceptionWindowId


class SetReceptionWindowsRequest(BaseSchema):
    windows: list[ReceptionWindowInput]
