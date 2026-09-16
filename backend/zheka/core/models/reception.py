from datetime import datetime, time
from typing import cast

from zheka.base import ZhekaMutableType
from zheka.core.enums import AppointmentStatus
from zheka.core.ids import (
    AppointmentId,
    HouseId,
    OrgId,
    ReceptionWindowId,
    RequestId,
    UserId,
)

_UNSET_AT = cast(datetime, None)
_UNSET_RECEPTION_WINDOW_ID = cast(ReceptionWindowId, None)
_UNSET_APPOINTMENT_ID = cast(AppointmentId, None)


class ReceptionWindow(ZhekaMutableType):
    id: ReceptionWindowId = _UNSET_RECEPTION_WINDOW_ID
    org_id: OrgId
    weekday: int
    time_from: time
    time_to: time
    slot_minutes: int


class Appointment(ZhekaMutableType):
    id: AppointmentId = _UNSET_APPOINTMENT_ID
    created_at: datetime = _UNSET_AT
    org_id: OrgId
    house_id: HouseId
    user_id: UserId
    request_id: RequestId | None = None
    starts_at: datetime
    status: AppointmentStatus
    reminder_sent_at: datetime | None = None
