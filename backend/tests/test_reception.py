import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser

from zheka.core.enums import (
    AppointmentStatus,
    EventType,
    RequestCategory,
    RequestChannel,
    RequestStatus,
    ResidentRole,
)
from zheka.core.errors import EntityNotFound, InvalidRequest, InvalidState
from zheka.core.ids import (
    AppointmentId,
    HouseId,
    MaxUserId,
    OrgId,
    RequestId,
    UserId,
)
from zheka.core.models import ReceptionWindow
from zheka.core.services.events import EventsService
from zheka.core.services.reception import (
    ReceptionService,
    ReceptionWindowDraft,
    expand_slots,
    horizon,
)
from zheka.infra.database.models import Event, Request, User
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.reception import ReceptionRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.events import events_table

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


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


def _window(
    *,
    weekday: int = 0,
    time_from: time = time(10, 0),
    time_to: time = time(18, 0),
    slot_minutes: int = 30,
) -> ReceptionWindow:
    return ReceptionWindow(
        org_id=OrgId(1),
        weekday=weekday,
        time_from=time_from,
        time_to=time_to,
        slot_minutes=slot_minutes,
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
    # послезавтра: сетка отдает только будущие слоты, а «сегодня в 10:00»
    # к моменту прогона уже может быть в прошлом
    return datetime.now(UTC).date() + timedelta(days=2)


def _moment(day: date, at: time = time(10, 0)) -> datetime:
    return datetime.combine(day, at, tzinfo=UTC)


async def _events(session: AsyncSession, type_: EventType) -> list[Event]:
    stmt = select(Event).where(events_table.c.type == type_)
    return list((await session.execute(stmt)).scalars().all())


async def _add_user(session: AsyncSession, name: str = "Сосед") -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name=name)
    session.add(user)
    await session.flush()
    return UserId(user.id)


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
    )
    session.add(request)
    await session.flush()
    return RequestId(request.id)


def test_a_window_that_divides_evenly_gives_every_slot() -> None:
    day = date(2026, 9, 21)

    slots = expand_slots(_window(), day)

    assert len(slots) == 16
    assert slots[0] == datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    assert slots[-1] == datetime(2026, 9, 21, 17, 30, tzinfo=UTC)


def test_a_window_that_does_not_divide_evenly_drops_the_tail() -> None:
    day = date(2026, 9, 21)
    window = _window(time_from=time(10, 0), time_to=time(11, 10), slot_minutes=30)

    slots = expand_slots(window, day)

    # 11:00 не помещается целиком до 11:10 и не предлагается
    assert slots == [
        datetime(2026, 9, 21, 10, 0, tzinfo=UTC),
        datetime(2026, 9, 21, 10, 30, tzinfo=UTC),
    ]


@pytest.mark.parametrize(
    ("time_from", "time_to"),
    [(time(18, 0), time(10, 0)), (time(10, 0), time(10, 0))],
)
def test_a_window_that_ends_before_it_starts_gives_nothing(
    time_from: time,
    time_to: time,
) -> None:
    window = _window(time_from=time_from, time_to=time_to)

    assert expand_slots(window, date(2026, 9, 21)) == []


def test_horizon_without_a_date_is_two_weeks() -> None:
    date_from, date_to = horizon(None)

    assert (date_to - date_from).days == 14
    assert horizon(date(2026, 9, 21)) == (date(2026, 9, 21), date(2026, 9, 21))


async def test_an_org_without_windows_answers_an_empty_grid(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)

    day = _some_day()

    assert await service.slots(fixture.house_id, day, day) == []


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

    slots = await service.slots(fixture.house_id, day, day)

    # 11:00 попадает в оба окна, но остается одним слотом
    assert [slot.starts_at for slot in slots] == [
        _moment(day, time(10, 0)),
        _moment(day, time(11, 0)),
        _moment(day, time(12, 0)),
        _moment(day, time(13, 0)),
    ]

    # в 11:00 принимают двое: мест в общем слоте столько, сколько дает
    # самое просторное из накрывших его окон
    shared = _moment(day, time(11, 0))
    await service.book(fixture.user_id, fixture.house_id, shared, None)
    neighbour = await _add_user(session)
    await service.book(neighbour, fixture.house_id, shared, None)

    third = await _add_user(session)
    with pytest.raises(InvalidState, match="занят"):
        await service.book(third, fixture.house_id, shared, None)


async def test_a_taken_slot_stays_in_the_grid_and_cannot_be_booked_twice(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    day = _some_day()
    starts_at = _moment(day)

    await service.book(fixture.user_id, fixture.house_id, starts_at, None)

    slots = {
        slot.starts_at: slot.is_free
        for slot in await service.slots(
            fixture.house_id,
            day,
            day,
        )
    }
    assert slots[starts_at] is False

    neighbour = await _add_user(session)
    with pytest.raises(InvalidState, match="занят"):
        await service.book(neighbour, fixture.house_id, starts_at, None)

    # занят именно этот слот, а не весь день организации
    await service.book(neighbour, fixture.house_id, _moment(day, time(10, 30)), None)


async def test_a_slot_outside_the_generated_set_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    day = _some_day()

    with pytest.raises(InvalidState, match="Такого слота нет"):
        await service.book(
            fixture.user_id,
            fixture.house_id,
            _moment(day, time(10, 7)),
            None,
        )


async def test_a_slot_in_the_past_is_not_offered(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    yesterday = datetime.now(UTC).date() - timedelta(days=1)

    assert await service.slots(fixture.house_id, yesterday, yesterday) == []


async def test_a_request_of_another_user_or_house_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    starts_at = _moment(_some_day())

    stranger = await _add_user(session)
    someone_elses = await _add_request(session, fixture.house_id, stranger)
    with pytest.raises(EntityNotFound, match="Заявка"):
        await service.book(
            fixture.user_id,
            fixture.house_id,
            starts_at,
            someone_elses,
        )

    another_house = await _add_request(session, other.house_id, fixture.user_id)
    with pytest.raises(EntityNotFound, match="Заявка"):
        await service.book(
            fixture.user_id,
            fixture.house_id,
            starts_at,
            another_house,
        )

    assert await service.mine(fixture.user_id) == []


async def test_a_linked_request_travels_to_the_record(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    request_id = await _add_request(session, fixture.house_id, fixture.user_id)

    booked = await service.book(
        fixture.user_id,
        fixture.house_id,
        _moment(_some_day()),
        request_id,
    )

    assert booked.appointment.request_id == request_id
    assert booked.org_phone == "+70000000000"
    # имя и квартиру заполняет только кабинет УК
    assert booked.user_name is None

    events = await _events(session, EventType.APPOINTMENT_BOOKED)

    assert len(events) == 1
    assert events[0].payload["has_request"] is True
    assert events[0].payload["appointment_id"] == booked.appointment.id


async def test_cancelling_frees_the_slot_for_the_next_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    day = _some_day()
    starts_at = _moment(day)

    booked = await service.book(fixture.user_id, fixture.house_id, starts_at, None)
    await service.cancel(AppointmentId(booked.appointment.id), fixture.user_id)

    slots = {
        slot.starts_at: slot.is_free
        for slot in await service.slots(fixture.house_id, day, day)
    }
    assert slots[starts_at] is True

    neighbour = await _add_user(session)
    again = await service.book(neighbour, fixture.house_id, starts_at, None)

    assert again.appointment.user_id == neighbour

    # «мои записи» - это записи жителя, а не всего дома
    mine = await service.mine(neighbour)

    assert [row.appointment.id for row in mine] == [again.appointment.id]
    # у первого жителя осталась только его отмененная запись
    assert [row.appointment.id for row in await service.mine(fixture.user_id)] == [
        booked.appointment.id
    ]


async def test_a_repeated_cancel_answers_ok_and_a_done_one_does_not(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)

    booked = await service.book(
        fixture.user_id,
        fixture.house_id,
        _moment(_some_day()),
        None,
    )
    appointment_id = AppointmentId(booked.appointment.id)
    await service.cancel(appointment_id, fixture.user_id)
    await service.cancel(appointment_id, fixture.user_id)

    booked.appointment.status = AppointmentStatus.DONE
    await session.flush()
    with pytest.raises(InvalidState, match="состоялся"):
        await service.cancel(appointment_id, fixture.user_id)


async def test_a_record_of_another_resident_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    booked = await service.book(
        fixture.user_id,
        fixture.house_id,
        _moment(_some_day()),
        None,
    )

    stranger = await _add_user(session)
    with pytest.raises(EntityNotFound, match="Запись"):
        await service.cancel(AppointmentId(booked.appointment.id), stranger)


async def test_the_office_list_carries_the_resident_and_the_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    day = _some_day()
    await service.book(fixture.user_id, fixture.house_id, _moment(day), None)

    rows = await service.today(fixture.org_id, day, fixture.house_id)

    assert len(rows) == 1
    assert rows[0].user_name == "Тест Тестов"
    assert rows[0].flat_number == "1"
    assert rows[0].address.endswith("Тестовая, 1")


async def test_the_office_list_of_a_foreign_house_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    service = _make_service(session)

    with pytest.raises(EntityNotFound, match="Дом"):
        await service.today(fixture.org_id, _some_day(), other.house_id)


async def test_an_appointment_of_another_house_stays_out_of_the_day(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    day = _some_day()
    await service.book(fixture.user_id, fixture.house_id, _moment(day), None)

    other_day = day + timedelta(days=1)

    assert await service.today(fixture.org_id, other_day, None) == []
    assert len(await service.today(fixture.org_id, day, None)) == 1


@pytest.mark.parametrize(
    ("weekday", "time_from", "time_to", "slot_minutes", "capacity"),
    [
        (7, time(10, 0), time(18, 0), 30, 1),
        (-1, time(10, 0), time(18, 0), 30, 1),
        (0, time(18, 0), time(10, 0), 30, 1),
        (0, time(10, 0), time(18, 0), 4, 1),
        (0, time(10, 0), time(18, 0), 241, 1),
        (0, time(10, 0), time(18, 0), 30, 0),
    ],
)
async def test_a_broken_window_is_rejected(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    weekday: int,
    time_from: time,
    time_to: time,
    slot_minutes: int,
    capacity: int,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)

    with pytest.raises(InvalidRequest):
        await service.set_windows(
            fixture.org_id,
            [
                ReceptionWindowDraft(
                    weekday=weekday,
                    time_from=time_from,
                    time_to=time_to,
                    slot_minutes=slot_minutes,
                    capacity=capacity,
                ),
            ],
        )


async def test_setting_windows_replaces_the_whole_grid(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)

    await service.set_windows(fixture.org_id, [_draft(0), _draft(1)])
    await service.set_windows(fixture.org_id, [_draft(3)])

    assert [window.weekday for window in await service.windows(fixture.org_id)] == [3]

    # пустой список - это законный «прием не ведем»
    await service.set_windows(fixture.org_id, [])

    assert await service.windows(fixture.org_id) == []


async def test_the_windows_of_another_org_stay_untouched(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    service = _make_service(session)

    await service.set_windows(fixture.org_id, [_draft(0)])
    await service.set_windows(other.org_id, [])

    assert len(await service.windows(fixture.org_id)) == 1


async def test_a_window_with_two_seats_takes_two_residents_and_no_third(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id, capacity=2)
    day = _some_day()
    starts_at = _moment(day)

    async def is_free() -> bool:
        slots = await service.slots(fixture.house_id, day, day)
        return {slot.starts_at: slot.is_free for slot in slots}[starts_at]

    await service.book(fixture.user_id, fixture.house_id, starts_at, None)

    assert await is_free() is True

    second = await _add_user(session)
    await service.book(second, fixture.house_id, starts_at, None)

    assert await is_free() is False

    third = await _add_user(session)
    with pytest.raises(InvalidState, match="занят"):
        await service.book(third, fixture.house_id, starts_at, None)


async def test_another_org_does_not_take_our_slot(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    # у соседней организации в тот же день недели просторнее: ее окна не
    # должны добавлять мест в наш слот
    await _open_every_day(service, other.org_id, capacity=3)
    day = _some_day()
    starts_at = _moment(day)

    await service.book(other.user_id, other.house_id, starts_at, None)

    slots = {
        slot.starts_at: slot.is_free
        for slot in await service.slots(fixture.house_id, day, day)
    }
    assert slots[starts_at] is True

    booked = await service.book(fixture.user_id, fixture.house_id, starts_at, None)

    assert booked.appointment.org_id == fixture.org_id

    # место в нашем слоте одно, и чужая запись его не занимает и не добавляет
    neighbour = await _add_user(session)
    with pytest.raises(InvalidState, match="занят"):
        await service.book(neighbour, fixture.house_id, starts_at, None)

    # день УК - это записи ее домов, а не всех организаций сразу
    rows = await service.today(fixture.org_id, day, None)

    assert [row.appointment.id for row in rows] == [booked.appointment.id]


async def test_a_cancelled_record_does_not_block_the_same_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    day = _some_day()
    starts_at = _moment(day)

    booked = await service.book(fixture.user_id, fixture.house_id, starts_at, None)
    await service.cancel(AppointmentId(booked.appointment.id), fixture.user_id)
    again = await service.book(fixture.user_id, fixture.house_id, starts_at, None)

    assert again.appointment.id != booked.appointment.id


async def test_a_resident_rebooking_a_one_seat_slot_hears_about_their_own_record(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    # вместимость в одно место - случай по умолчанию, и «слот занят» про
    # собственную запись жителю ничего не объясняет
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    await _open_every_day(service, fixture.org_id)
    starts_at = _moment(_some_day())

    await service.book(fixture.user_id, fixture.house_id, starts_at, None)

    with pytest.raises(InvalidState, match="уже записаны"):
        await service.book(fixture.user_id, fixture.house_id, starts_at, None)
