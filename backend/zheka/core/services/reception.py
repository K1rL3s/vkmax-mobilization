from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

from zheka.base import ZhekaType
from zheka.core.enums import AppointmentStatus, EventType
from zheka.core.errors import (
    HOUSE_NOT_FOUND,
    REQUEST_NOT_FOUND,
    EntityNotFound,
    InvalidRequest,
    InvalidState,
)
from zheka.core.ids import AppointmentId, HouseId, OrgId, RequestId, UserId
from zheka.core.models import Appointment, ReceptionWindow
from zheka.core.services.events import EventsService
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.reception import ReceptionRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

RECEPTION_HORIZON_DAYS = 14
LAST_WEEKDAY = 6
MIN_SLOT_MINUTES = 5
MAX_SLOT_MINUTES = 240

APPOINTMENT_NOT_FOUND = "Запись на прием не найдена"
SLOT_TAKEN = "Слот уже занят"
SLOT_UNKNOWN = "Такого слота нет"
ALREADY_DONE = "Прием уже состоялся"
ALREADY_BOOKED = "Вы уже записаны на это время"
BAD_WEEKDAY = "День недели задается числом от 0 (понедельник) до 6"
BAD_TIME_RANGE = "Прием должен начинаться раньше, чем заканчивается"
BAD_SLOT_MINUTES = f"Длина слота - от {MIN_SLOT_MINUTES} до {MAX_SLOT_MINUTES} минут"
BAD_CAPACITY = "В слот должен помещаться хотя бы один житель"


class ReceptionSlot(ZhekaType):
    starts_at: datetime
    is_free: bool


class AppointmentData(ZhekaType):
    appointment: Appointment
    address: str
    org_address: str
    org_phone: str
    user_name: str | None = None
    flat_number: str | None = None


class ReceptionWindowDraft(ZhekaType):
    weekday: int
    time_from: time
    time_to: time
    slot_minutes: int
    capacity: int = 1


def expand_slots(window: ReceptionWindow, day: date) -> list[datetime]:
    if window.slot_minutes <= 0:
        return []
    step = timedelta(minutes=window.slot_minutes)
    starts_at = datetime.combine(day, window.time_from, tzinfo=UTC)
    ends_at = datetime.combine(day, window.time_to, tzinfo=UTC)
    return [
        starts_at + step * number for number in range((ends_at - starts_at) // step)
    ]


def slot_capacities(
    windows: Sequence[ReceptionWindow], date_from: date, date_to: date
) -> dict[datetime, int]:
    capacities: dict[datetime, int] = {}
    day = date_from
    while day <= date_to:
        for window in windows:
            if window.weekday != day.weekday():
                continue
            for moment in expand_slots(window, day):
                capacities[moment] = max(capacities.get(moment, 0), window.capacity)
        day += timedelta(days=1)
    return capacities


def horizon(on_date: date | None) -> tuple[date, date]:
    if on_date is not None:
        return on_date, on_date
    today = datetime.now(UTC).date()
    return today, today + timedelta(days=RECEPTION_HORIZON_DAYS)


def as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


class ReceptionService:
    __slots__ = (
        "_events",
        "_houses",
        "_orgs",
        "_reception",
        "_requests",
        "_residents",
        "_users",
    )

    def __init__(
        self,
        reception_repo: ReceptionRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        residents_repo: ResidentsRepo,
        requests_repo: RequestsRepo,
        users_repo: UsersRepo,
        events_service: EventsService,
    ) -> None:
        self._reception = reception_repo
        self._houses = houses_repo
        self._orgs = orgs_repo
        self._residents = residents_repo
        self._requests = requests_repo
        self._users = users_repo
        self._events = events_service

    async def slots(
        self, house_id: HouseId, date_from: date, date_to: date
    ) -> list[ReceptionSlot]:
        house = await self._houses.get(house_id)
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        if house.org_id is None:
            return []
        org_id = house.org_id
        windows = await self._reception.list_windows(org_id)
        taken = await self._reception.taken_counts(org_id, date_from, date_to)
        capacities = slot_capacities(windows, date_from, date_to)

        now = datetime.now(UTC)
        return [
            ReceptionSlot(starts_at=moment, is_free=taken.get(moment, 0) < capacity)
            for moment, capacity in sorted(capacities.items())
            if moment > now
        ]

    async def book(
        self,
        user_id: UserId,
        house_id: HouseId,
        starts_at: datetime,
        request_id: RequestId | None,
    ) -> AppointmentData:
        house = await self._houses.get(house_id)
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        if house.org_id is None:
            raise InvalidState(SLOT_UNKNOWN)
        org_id = house.org_id

        moment = as_utc(starts_at)
        day = moment.date()
        windows = await self._reception.lock_windows(org_id, day.weekday())
        capacity = slot_capacities(windows, day, day).get(moment)
        if capacity is None or moment <= datetime.now(UTC):
            raise InvalidState(SLOT_UNKNOWN)
        if await self._reception.has_booking(org_id, user_id, moment):
            raise InvalidState(ALREADY_BOOKED)
        if await self._reception.count_booked(org_id, moment) >= capacity:
            raise InvalidState(SLOT_TAKEN)

        if request_id is not None:
            request = await self._requests.get(request_id)
            if (
                request is None
                or request.author_user_id != user_id
                or request.house_id != house_id
            ):
                raise EntityNotFound(REQUEST_NOT_FOUND)

        appointment = await self._reception.create_appointment(
            org_id, house_id, user_id, moment, request_id
        )
        await self._events.record(
            EventType.APPOINTMENT_BOOKED,
            user_id=user_id,
            appointment_id=appointment.id,
            has_request=request_id is not None,
        )
        [row] = await self._decorate([appointment], with_people=False)
        return row

    async def cancel(self, appointment_id: AppointmentId, user_id: UserId) -> None:
        appointment = await self._reception.get_for_user(appointment_id, user_id)
        if appointment is None:
            raise EntityNotFound(APPOINTMENT_NOT_FOUND)
        if appointment.status is AppointmentStatus.DONE:
            raise InvalidState(ALREADY_DONE)
        if appointment.status is AppointmentStatus.CANCELLED:
            return
        await self._reception.cancel_appointment(appointment)

    async def mine(self, user_id: UserId) -> list[AppointmentData]:
        appointments = await self._reception.list_for_user(user_id)
        return await self._decorate(appointments, with_people=False)

    async def today(
        self, org_id: OrgId, on_date: date | None, house_id: HouseId | None
    ) -> list[AppointmentData]:
        if (
            house_id is not None
            and await self._houses.get_for_org(house_id, org_id) is None
        ):
            raise EntityNotFound(HOUSE_NOT_FOUND)
        day = on_date or datetime.now(UTC).date()
        appointments = await self._reception.list_appointments(org_id, day, house_id)
        return await self._decorate(appointments, with_people=True)

    async def windows(self, org_id: OrgId) -> Sequence[ReceptionWindow]:
        return await self._reception.list_windows(org_id)

    async def set_windows(
        self, org_id: OrgId, drafts: Sequence[ReceptionWindowDraft]
    ) -> Sequence[ReceptionWindow]:
        for draft in drafts:
            if not 0 <= draft.weekday <= LAST_WEEKDAY:
                raise InvalidRequest(BAD_WEEKDAY)
            if draft.time_from >= draft.time_to:
                raise InvalidRequest(BAD_TIME_RANGE)
            if not MIN_SLOT_MINUTES <= draft.slot_minutes <= MAX_SLOT_MINUTES:
                raise InvalidRequest(BAD_SLOT_MINUTES)
            if draft.capacity < 1:
                raise InvalidRequest(BAD_CAPACITY)
        return await self._reception.replace_windows(
            org_id,
            [
                ReceptionWindow(
                    org_id=org_id,
                    weekday=draft.weekday,
                    time_from=draft.time_from,
                    time_to=draft.time_to,
                    slot_minutes=draft.slot_minutes,
                    capacity=draft.capacity,
                )
                for draft in drafts
            ],
        )

    async def _decorate(
        self, appointments: Sequence[Appointment], *, with_people: bool
    ) -> list[AppointmentData]:
        if not appointments:
            return []
        house_ids = {row.house_id for row in appointments}
        houses = {
            house.id: house for house in await self._houses.list_by_ids(house_ids)
        }
        orgs = {
            org.id: org
            for org in await self._orgs.list_by_ids(
                {row.org_id for row in appointments}
            )
        }
        names, flat_numbers = (
            await self._people(appointments) if with_people else ({}, {})
        )

        rows = []
        for appointment in appointments:
            house = houses[appointment.house_id]
            org = orgs[appointment.org_id]
            user_id = appointment.user_id
            rows.append(
                AppointmentData(
                    appointment=appointment,
                    address=house.address,
                    org_address=org.address,
                    org_phone=org.phone,
                    user_name=names.get(user_id),
                    flat_number=flat_numbers.get((user_id, appointment.house_id)),
                )
            )
        return rows

    async def _people(
        self, appointments: Sequence[Appointment]
    ) -> tuple[dict[UserId, str], dict[tuple[UserId, HouseId], str | None]]:
        user_ids = {row.user_id for row in appointments}
        house_ids = {row.house_id for row in appointments}
        names = {user.id: user.name for user in await self._users.list_by_ids(user_ids)}
        residents = await self._residents.list_for_houses_and_users(house_ids, user_ids)
        numbers = {
            flat.id: flat.number
            for flat in await self._houses.list_flats_by_ids(
                {
                    resident.flat_id
                    for resident in residents
                    if resident.flat_id is not None
                }
            )
        }
        flat_numbers = {
            (resident.user_id, resident.house_id): (
                numbers.get(resident.flat_id)
                if resident.flat_id is not None
                else resident.flat_number
            )
            for resident in residents
        }
        return names, flat_numbers
