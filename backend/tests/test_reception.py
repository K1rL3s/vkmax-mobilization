from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import Fixture, add_user, events_of, freeze_now

from zheka.api.schemas.reception import AppointmentItem
from zheka.core.enums import (
    AppointmentStatus,
    EventType,
    RequestCategory,
    RequestChannel,
    RequestStatus,
    ResidentRole,
)
from zheka.core.errors import EntityNotFound, InvalidRequest, InvalidState
from zheka.core.ids import HouseId, OrgId, RequestId, UserId
from zheka.core.models import ReceptionWindow
from zheka.core.services.events import EventsService
from zheka.core.services.reception import (
    ReceptionService,
    ReceptionWindowDraft,
)
from zheka.infra.database.models import Request
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.reception import ReceptionRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

MOSCOW = ZoneInfo("Europe/Moscow")


def _make_service(session: AsyncSession) -> ReceptionService:
    return ReceptionService(
        ReceptionRepo(session),
        HousesRepo(session),
        OrgsRepo(session),
        ResidentsRepo(session),
        RequestsRepo(session),
        UsersRepo(session),
        EventsService(EventsRepo(session)),
    )


def _draft(weekday: int, *, capacity: int = 1) -> ReceptionWindowDraft:
    return ReceptionWindowDraft(
        weekday=weekday,
        time_from=time(10, 0),
        time_to=time(18, 0),
        slot_minutes=30,
        capacity=capacity,
    )


async def _open_every_day(
    service: ReceptionService,
    org_id: OrgId,
    *,
    capacity: int = 1,
) -> None:
    await service.set_windows(
        org_id,
        [_draft(weekday, capacity=capacity) for weekday in range(7)],
    )


def _some_day() -> date:
    return datetime.now(UTC).date() + timedelta(days=2)


def _moment(day: date, at: time = time(10, 0)) -> datetime:
    return datetime.combine(day, at, tzinfo=MOSCOW)


async def _add_request(
    session: AsyncSession,
    house_id: HouseId,
    author_user_id: UserId,
) -> RequestId:
    request = Request(
        house_id=house_id,
        author_user_id=author_user_id,
        category=RequestCategory.OTHER,
        description="Течет кран",
        status=RequestStatus.NEW,
        channel=RequestChannel.MINIAPP,
        deadline_at=datetime.now(UTC),
    )
    session.add(request)
    await session.flush()
    return request.id


def test_a_window_expands_into_whole_slots_in_utc() -> None:
    window = ReceptionWindow(
        org_id=OrgId(1),
        weekday=0,
        time_from=time(10, 0),
        time_to=time(11, 10),
        slot_minutes=30,
    )

    slots = window.expand_slots(date(2026, 9, 21), MOSCOW)

    assert slots == [
        datetime(2026, 9, 21, 7, tzinfo=UTC),
        datetime(2026, 9, 21, 7, 30, tzinfo=UTC),
    ]
    assert {slot.tzinfo for slot in slots} == {UTC}


async def test_slots_without_a_date_run_two_weeks_ahead(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze_now(
        monkeypatch,
        "zheka.core.services.reception",
        datetime(2026, 9, 14, 22, tzinfo=UTC),
    )
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)

    slots = await service.slots(fixture.house_id, None)

    assert slots[-1].starts_at == _moment(date(2026, 9, 29), time(17, 30))


async def test_several_windows_on_one_weekday_are_expanded_together(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    day = _some_day()
    await service.set_windows(
        fixture.org_id,
        [
            ReceptionWindowDraft(
                weekday=day.weekday(),
                time_from=time(10, 0),
                time_to=time(14, 0),
                slot_minutes=60,
                capacity=2,
            ),
            ReceptionWindowDraft(
                weekday=day.weekday(),
                time_from=time(11, 0),
                time_to=time(12, 0),
                slot_minutes=60,
            ),
        ],
    )

    slots = await service.slots(fixture.house_id, day)

    assert [slot.starts_at for slot in slots] == [
        _moment(day, time(10, 0)),
        _moment(day, time(11, 0)),
        _moment(day, time(12, 0)),
        _moment(day, time(13, 0)),
    ]

    shared = _moment(day, time(11, 0))

    async def is_free() -> bool:
        slots = await service.slots(fixture.house_id, day)
        return {slot.starts_at: slot.is_free for slot in slots}[shared]

    await service.book(fixture.user_id, fixture.house_id, shared, None)

    assert await is_free() is True

    neighbour = await add_user(session)
    await service.book(neighbour, fixture.house_id, shared, None)

    assert await is_free() is False

    third = await add_user(session)
    with pytest.raises(InvalidState, match="занят"):
        await service.book(third, fixture.house_id, shared, None)


async def test_a_slot_off_the_grid_or_in_the_past_is_neither_offered_nor_booked(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    day = _some_day()

    assert await service.slots(fixture.house_id, day) == []

    await _open_every_day(service, fixture.org_id)
    yesterday = datetime.now(UTC).date() - timedelta(days=1)

    assert await service.slots(fixture.house_id, yesterday) == []

    for moment in (_moment(day, time(10, 7)), _moment(yesterday)):
        with pytest.raises(InvalidState, match="Такого слота нет"):
            await service.book(fixture.user_id, fixture.house_id, moment, None)


async def test_a_request_of_another_user_or_house_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    starts_at = _moment(_some_day())

    stranger = await add_user(session)
    someone_elses = await _add_request(session, fixture.house_id, stranger)
    with pytest.raises(EntityNotFound, match="Заявка"):
        await service.book(fixture.user_id, fixture.house_id, starts_at, someone_elses)

    another_house = await _add_request(session, other.house_id, fixture.user_id)
    with pytest.raises(EntityNotFound, match="Заявка"):
        await service.book(fixture.user_id, fixture.house_id, starts_at, another_house)

    assert await service.mine(fixture.user_id) == []


async def test_a_linked_request_travels_to_the_record(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    request_id = await _add_request(session, fixture.house_id, fixture.user_id)

    booked = AppointmentItem.of(
        await service.book(
            fixture.user_id,
            fixture.house_id,
            _moment(_some_day()),
            request_id,
        ),
    )

    assert booked.request_id == request_id
    assert booked.org_phone == "+70000000000"
    assert booked.user_name is None

    events = await events_of(session, EventType.APPOINTMENT_BOOKED)

    assert len(events) == 1
    assert events[0].payload["has_request"] is True
    assert events[0].payload["appointment_id"] == booked.id


async def test_a_resident_cancels_only_their_own_record_and_frees_the_slot(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    day = _some_day()
    starts_at = _moment(day)

    booked = await service.book(fixture.user_id, fixture.house_id, starts_at, None)
    with pytest.raises(InvalidState, match="уже записаны"):
        await service.book(fixture.user_id, fixture.house_id, starts_at, None)
    later = await service.book(
        fixture.user_id,
        fixture.house_id,
        _moment(day, time(10, 30)),
        None,
    )

    appointment_id = booked.appointment.id
    stranger = await add_user(session)
    with pytest.raises(EntityNotFound, match="Запись"):
        await service.cancel(appointment_id, stranger)

    await service.cancel(appointment_id, fixture.user_id)
    await service.cancel(appointment_id, fixture.user_id)
    slots = {
        slot.starts_at: slot.is_free
        for slot in await service.slots(fixture.house_id, day)
    }

    assert slots[starts_at] is True

    again = await service.book(fixture.user_id, fixture.house_id, starts_at, None)

    assert {row.appointment.id for row in await service.mine(fixture.user_id)} == {
        appointment_id,
        later.appointment.id,
        again.appointment.id,
    }
    assert await service.mine(stranger) == []

    booked.appointment.status = AppointmentStatus.DONE
    await session.flush()
    with pytest.raises(InvalidState, match="состоялся"):
        await service.cancel(appointment_id, fixture.user_id)


async def test_the_office_list_carries_the_resident_and_the_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    other = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    day = _some_day()
    await service.book(fixture.user_id, fixture.house_id, _moment(day), None)

    [row] = await service.today(fixture.org_id, day, fixture.house_id)
    item = AppointmentItem.of(row)

    assert (item.user_name, item.flat_number) == ("Тест Тестов", "1")
    assert (item.address, item.org_address) == (
        "Тестоград, Тестовая, 1",
        "Тестовая область, Тестоград, Тестовая, 1",
    )
    assert (item.org_id, item.house_id) == (fixture.org_id, fixture.house_id)
    for other_day in (day - timedelta(days=1), day + timedelta(days=1)):
        assert await service.today(fixture.org_id, other_day, None) == []

    with pytest.raises(EntityNotFound, match="Дом"):
        await service.today(fixture.org_id, day, other.house_id)


@pytest.mark.parametrize(
    "broken",
    [
        {"weekday": 7},
        {"weekday": -1},
        {"time_from": time(18, 0), "time_to": time(10, 0)},
        {"slot_minutes": 4},
        {"slot_minutes": 241},
        {"capacity": 0},
    ],
)
async def test_a_broken_window_is_rejected(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broken: dict[str, Any],
) -> None:
    fixture = await make_org_house_flat_user()

    with pytest.raises(InvalidRequest):
        await _make_service(session).set_windows(
            fixture.org_id,
            [replace(_draft(0), **broken)],
        )


async def test_setting_windows_replaces_the_whole_grid(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    service = _make_service(session)

    await service.set_windows(fixture.org_id, [_draft(0), _draft(1)])
    await service.set_windows(fixture.org_id, [_draft(3)])
    await service.set_windows(other.org_id, [])

    assert [window.weekday for window in await service.windows(fixture.org_id)] == [3]

    await service.set_windows(fixture.org_id, [])

    assert await service.windows(fixture.org_id) == []


async def test_another_org_does_not_take_our_slot(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    await _open_every_day(service, other.org_id, capacity=3)
    day = _some_day()
    starts_at = _moment(day)

    await service.book(other.user_id, other.house_id, starts_at, None)

    slots = {
        slot.starts_at: slot.is_free
        for slot in await service.slots(fixture.house_id, day)
    }
    assert slots[starts_at] is True

    booked = await service.book(fixture.user_id, fixture.house_id, starts_at, None)

    assert booked.appointment.org_id == fixture.org_id

    neighbour = await add_user(session)
    with pytest.raises(InvalidState, match="занят"):
        await service.book(neighbour, fixture.house_id, starts_at, None)

    rows = await service.today(fixture.org_id, day, None)

    assert [row.appointment.id for row in rows] == [booked.appointment.id]

    await service.book(neighbour, fixture.house_id, _moment(day, time(10, 30)), None)


async def test_a_naive_time_books_the_slot_of_the_office_clock(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    day = _some_day()

    booked = await service.book(
        fixture.user_id,
        fixture.house_id,
        datetime.combine(day, time(10)),
        None,
    )

    assert booked.appointment.starts_at == datetime.combine(day, time(7), UTC)


async def test_the_office_day_is_counted_on_the_office_clock(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    day = _some_day()
    await service.set_windows(
        fixture.org_id,
        [
            ReceptionWindowDraft(
                weekday=day.weekday(),
                time_from=time(0, 30),
                time_to=time(1, 30),
                slot_minutes=60,
            ),
        ],
    )
    [slot] = await service.slots(fixture.house_id, day)
    booked = await service.book(fixture.user_id, fixture.house_id, slot.starts_at, None)

    [row] = await service.today(fixture.org_id, day, None)
    [taken] = await service.slots(fixture.house_id, day)

    assert row.appointment.id == booked.appointment.id
    assert taken.is_free is False
