from datetime import UTC, date, datetime, time, timedelta, tzinfo

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.enums import AppointmentStatus
from zheka.core.ids import (
    AppointmentId,
    HouseId,
    OrgId,
    ReceptionWindowId,
    RequestId,
    UserId,
)


class ReceptionWindow(ZhekaMutableType):
    id: ReceptionWindowId = UNSET
    org_id: OrgId
    weekday: int
    time_from: time
    time_to: time
    slot_minutes: int
    capacity: int = 1

    def expand_slots(self, day: date, zone: tzinfo) -> list[datetime]:
        step = timedelta(minutes=self.slot_minutes)
        starts_at = datetime.combine(day, self.time_from, tzinfo=zone)
        ends_at = datetime.combine(day, self.time_to, tzinfo=zone)
        return [
            (starts_at + step * number).astimezone(UTC)
            for number in range((ends_at - starts_at) // step)
        ]


class Appointment(ZhekaMutableType):
    id: AppointmentId = UNSET
    created_at: datetime = UNSET
    org_id: OrgId
    house_id: HouseId
    user_id: UserId
    request_id: RequestId | None = None
    starts_at: datetime
    status: AppointmentStatus
    reminder_sent_at: datetime | None = None
