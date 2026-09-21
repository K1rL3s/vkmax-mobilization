import secrets
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import InMemoryBroker

from tests.conftest import RecordingBroker, make_notifications_service

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.broker.tasks.reminders import (
    close_expired_polls,
    remind_appointments,
    remind_polls,
    remind_readings,
    warn_verification,
)
from zheka.core.enums import (
    AppointmentStatus,
    ChatStatus,
    EventType,
    MeterType,
    NotificationCategory,
    PollStatus,
    ResidentRole,
    ResidentStatus,
)
from zheka.core.ids import (
    FlatId,
    HouseId,
    MaxChatId,
    MaxUserId,
    MeterId,
    OrgId,
    PollId,
    UserId,
)
from zheka.core.services.events import EventsService
from zheka.core.services.readings import current_period
from zheka.core.services.reminders import (
    ReadingReminder,
    RemindersService,
    reading_reminder,
)
from zheka.infra.database.models import (
    Appointment,
    Chat,
    Flat,
    House,
    Meter,
    OrgSettings,
    Organization,
    Poll,
    PollOption,
    PollVote,
    Reading,
    Resident,
    User,
)
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.reception import ReceptionRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.tables.events import events_table
from zheka.infra.database.tables.houses import houses_table
from zheka.infra.database.tables.meters import meters_table
from zheka.infra.database.tables.polls import polls_table


def _settings(
    day_from: int = 15, day_to: int = 25, *, always_open: bool = False
) -> OrgSettings:
    return OrgSettings(
        org_id=OrgId(1),
        meter_window_day_from=day_from,
        meter_window_day_to=day_to,
        meter_window_always_open=always_open,
    )


@pytest.mark.parametrize(
    ("today", "settings", "expected"),
    [
        (date(2026, 9, 15), _settings(), ReadingReminder.OPEN),
        (date(2026, 9, 23), _settings(), ReadingReminder.CLOSING),
        (date(2026, 9, 20), _settings(), None),
        # у всегда открытого окна закрытие - конец месяца, а в феврале он 28-го
        (date(2026, 2, 26), _settings(always_open=True), ReadingReminder.CLOSING),
        (date(2026, 9, 28), _settings(always_open=True), ReadingReminder.CLOSING),
        (date(2026, 9, 1), None, ReadingReminder.OPEN),
        # окно 25-1 закрывается 1 октября, за два дня до этого - 29 сентября
        (date(2026, 9, 29), _settings(25, 1), ReadingReminder.CLOSING),
        # окно 1-2 внутри месяца: конец сентября - не канун его закрытия
        (date(2026, 9, 30), _settings(1, 2), None),
        # канун закрытия короткого окна - день до его открытия
        (date(2026, 9, 14), _settings(15, 16), None),
        (date(2026, 9, 13), _settings(15, 15), None),
        (date(2026, 2, 27), _settings(28, 1), None),
    ],
)
def test_the_reading_reminder_day(
    today: date, settings: OrgSettings | None, expected: ReadingReminder | None
) -> None:
    assert reading_reminder(today, settings) is expected


async def _run(broker: InMemoryBroker, task: Any) -> None:
    sent = await task.kicker().with_broker(broker).kiq()
    result = await sent.wait_result(timeout=5)
    assert not result.is_err, result.error


def _to_users(bot_broker: RecordingBroker, user_id: UserId) -> list[dict[str, Any]]:
    return [
        kwargs
        for kwargs in bot_broker.enqueued(TaskName.BROADCAST_TO_USERS)
        if user_id in kwargs["user_ids"]
    ]


def _today() -> date:
    return datetime.now(UTC).date()


async def _house(
    session: AsyncSession, settings: dict[str, Any] | None = None
) -> HouseId:
    org = Organization(
        name=f"УК {secrets.token_hex(4)}",
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Тестовая область, Тестоград, Тестовая, 1",
    )
    session.add(org)
    await session.flush()
    if settings is not None:
        session.add(OrgSettings(org_id=org.id, **settings))
    house = House(
        org_id=org.id,
        region="Тестовая область",
        city="Тестоград",
        street="Напоминательная",
        building=secrets.token_hex(2),
        cadastral_no=secrets.token_hex(8),
        chat_binding_code=secrets.token_hex(4),
    )
    session.add(house)
    await session.flush()
    house_id = house.id
    await session.commit()
    return house_id


async def _resident(
    session: AsyncSession,
    house_id: HouseId,
    *,
    verified: bool = True,
    role: ResidentRole = ResidentRole.OWNER,
    status: ResidentStatus = ResidentStatus.ACTIVE,
    with_flat: bool = True,
    flat_id: FlatId | None = None,
    user_id: UserId | None = None,
) -> tuple[FlatId, UserId]:
    if flat_id is None:
        flat = Flat(house_id=house_id, number=secrets.token_hex(2))
        session.add(flat)
        await session.flush()
        flat_id = flat.id
    if user_id is None:
        user = User(max_user_id=MaxUserId(secrets.randbits(40)), name="Житель")
        session.add(user)
        await session.flush()
        user_id = user.id
    session.add(
        Resident(
            user_id=user_id,
            house_id=house_id,
            flat_id=flat_id if with_flat else None,
            role=role,
            can_vote=role is ResidentRole.OWNER,
            verified_at=datetime.now(UTC) if verified else None,
            status=status,
        )
    )
    await session.commit()
    return flat_id, user_id


async def _meter(
    session: AsyncSession,
    flat_id: FlatId,
    *,
    due: date | None = None,
    warned_at: date | None = None,
) -> MeterId:
    meter = Meter(
        flat_id=flat_id,
        type=MeterType.COLD_WATER,
        serial=secrets.token_hex(4),
        next_verification_date=due,
        verification_warned_at=warned_at,
    )
    session.add(meter)
    await session.flush()
    meter_id = meter.id
    await session.commit()
    return meter_id


async def _reading_house(session: AsyncSession) -> HouseId:
    # окно открывается сегодня, каким бы ни был день запуска
    day = _today().day
    return await _house(
        session, {"meter_window_day_from": day, "meter_window_day_to": day}
    )


async def _submitted(
    session: AsyncSession,
    meter_id: MeterId,
    user_id: UserId,
    period: date | None = None,
) -> None:
    session.add(
        Reading(
            meter_id=meter_id,
            period=current_period(_today()) if period is None else period,
            values={"single": 1000},
            ocr_used=False,
            ocr_accepted=False,
            is_below_previous=False,
            submitted_at=datetime.now(UTC),
            submitted_by=user_id,
        )
    )
    await session.commit()


async def test_the_reading_reminder_goes_once_to_a_flat_that_did_not_submit(
    bot_session: AsyncSession, task_broker: InMemoryBroker, bot_broker: RecordingBroker
) -> None:
    house_id = await _reading_house(bot_session)
    lagging_flat, lagging = await _resident(bot_session, house_id)
    done_flat, done = await _resident(bot_session, house_id)
    unverified_flat, unverified = await _resident(bot_session, house_id, verified=False)
    await _meter(bot_session, lagging_flat)
    await _meter(bot_session, unverified_flat)
    await _submitted(bot_session, await _meter(bot_session, done_flat), done)

    await _run(task_broker, remind_readings)
    await _run(task_broker, remind_readings)

    [queued] = _to_users(bot_broker, lagging)
    # уровень разрешает рассылка, и OFF глушит ее только у необязательного
    # сообщения своей категории
    assert queued["category"] == NotificationCategory.METERS.value
    assert queued["mandatory"] is False
    assert _to_users(bot_broker, done) == []
    assert _to_users(bot_broker, unverified) == []


async def _poll(
    session: AsyncSession,
    house_id: HouseId,
    ends_in: timedelta,
    status: PollStatus = PollStatus.ACTIVE,
) -> PollId:
    author = User(max_user_id=MaxUserId(secrets.randbits(40)), name="Председатель")
    session.add(author)
    await session.flush()
    now = datetime.now(UTC)
    poll = Poll(
        house_id=house_id,
        created_by_user_id=author.id,
        created_by_role="chairman",
        title="Ремонт подъезда",
        starts_at=now - timedelta(days=5),
        ends_at=now + ends_in,
        status=status,
    )
    session.add(poll)
    await session.flush()
    poll_id = poll.id
    await session.commit()
    return poll_id


async def _vote(
    session: AsyncSession,
    poll_id: PollId,
    flat_id: FlatId,
    user_id: UserId,
    *,
    counted: bool = True,
) -> None:
    option = PollOption(poll_id=poll_id, text="За", position=0)
    session.add(option)
    await session.flush()
    session.add(
        PollVote(
            poll_id=poll_id,
            option_id=option.id,
            user_id=user_id,
            flat_id=flat_id,
            counted_by_area=counted,
        )
    )
    await session.commit()


@pytest.mark.parametrize(
    ("ends_in", "status", "reminded"),
    [
        (timedelta(hours=24), PollStatus.ACTIVE, True),
        (timedelta(hours=72), PollStatus.ACTIVE, False),
        (timedelta(hours=-1), PollStatus.ACTIVE, False),
        (timedelta(hours=24), PollStatus.CLOSED, False),
    ],
)
async def test_a_poll_is_reminded_in_its_last_two_days(
    bot_session: AsyncSession,
    task_broker: InMemoryBroker,
    bot_broker: RecordingBroker,
    ends_in: timedelta,
    status: PollStatus,
    reminded: bool,
) -> None:
    house_id = await _house(bot_session)
    _, user_id = await _resident(bot_session, house_id)
    await _poll(bot_session, house_id, ends_in, status)

    await _run(task_broker, remind_polls)

    assert bool(_to_users(bot_broker, user_id)) is reminded


async def test_the_poll_reminder_goes_once_only_to_flats_without_a_vote(
    bot_session: AsyncSession, task_broker: InMemoryBroker, bot_broker: RecordingBroker
) -> None:
    house_id = await _house(bot_session)
    _, waiting = await _resident(bot_session, house_id)
    voted_flat, voted = await _resident(bot_session, house_id)
    _, flatmate = await _resident(bot_session, house_id, flat_id=voted_flat)
    _, tenant = await _resident(bot_session, house_id, role=ResidentRole.TENANT)
    _, blocked = await _resident(bot_session, house_id, status=ResidentStatus.BLOCKED)
    _, flatless = await _resident(bot_session, house_id, with_flat=False)
    poll_id = await _poll(bot_session, house_id, timedelta(hours=24))
    await _vote(bot_session, poll_id, voted_flat, voted)

    await _run(task_broker, remind_polls)
    await _run(task_broker, remind_polls)

    [queued] = _to_users(bot_broker, waiting)
    assert {voted, flatmate, tenant, blocked, flatless}.isdisjoint(queued["user_ids"])
    assert queued["category"] == NotificationCategory.ANNOUNCEMENTS.value
    assert queued["mandatory"] is False


async def _chat(session: AsyncSession, house_id: HouseId, *, bound: bool) -> MaxChatId:
    chat_id = MaxChatId(-secrets.randbits(40))
    session.add(
        Chat(
            chat_id=chat_id,
            house_id=house_id,
            title="Дом",
            bot_is_admin=True,
            bound_at=datetime.now(UTC) if bound else None,
            status=ChatStatus.ACTIVE,
        )
    )
    await session.commit()
    return chat_id


async def test_the_poll_reminder_goes_into_the_bound_chat_only(
    bot_session: AsyncSession, task_broker: InMemoryBroker, bot_broker: RecordingBroker
) -> None:
    house_id = await _house(bot_session)
    bound = await _chat(bot_session, house_id, bound=True)
    unbound = await _chat(bot_session, house_id, bound=False)
    await _poll(bot_session, house_id, timedelta(hours=24))

    await _run(task_broker, remind_polls)

    chat_ids = [
        chat_id
        for kwargs in bot_broker.enqueued(TaskName.BROADCAST_TO_CHATS)
        for chat_id in kwargs["chat_ids"]
    ]
    assert bound in chat_ids
    assert unbound not in chat_ids


async def _poll_status(session: AsyncSession, poll_id: PollId) -> PollStatus:
    stmt = select(polls_table.c.status).where(polls_table.c.id == poll_id)
    status: PollStatus = (await session.execute(stmt)).scalar_one()
    return status


async def test_an_expired_poll_is_closed_and_a_running_one_is_not(
    bot_session: AsyncSession, task_broker: InMemoryBroker
) -> None:
    house_id = await _house(bot_session)
    expired = await _poll(bot_session, house_id, timedelta(minutes=-1))
    running = await _poll(bot_session, house_id, timedelta(hours=1))

    await _run(task_broker, close_expired_polls)

    assert await _poll_status(bot_session, expired) is PollStatus.CLOSED
    assert await _poll_status(bot_session, running) is PollStatus.ACTIVE


async def _warned_at(session: AsyncSession, meter_id: MeterId) -> date | None:
    stmt = select(meters_table.c.verification_warned_at).where(
        meters_table.c.id == meter_id
    )
    warned: date | None = (await session.execute(stmt)).scalar_one()
    return warned


def _texts(bot_broker: RecordingBroker, user_id: UserId) -> list[str]:
    return [kwargs["text"] for kwargs in _to_users(bot_broker, user_id)]


@pytest.mark.parametrize(
    ("due_in", "warned_ago", "expected"),
    [
        (10, None, "{due:%d.%m.%Y} истекает поверка"),
        (0, 30, "Истекла поверка"),
        # обе стадии старой даты пройдены, и новая дата начинает их заново
        (10, 365, "{due:%d.%m.%Y} истекает поверка"),
    ],
)
async def test_each_verification_warning_goes_once(
    bot_session: AsyncSession,
    task_broker: InMemoryBroker,
    bot_broker: RecordingBroker,
    due_in: int,
    warned_ago: int | None,
    expected: str,
) -> None:
    house_id = await _house(bot_session)
    flat_id, user_id = await _resident(bot_session, house_id)
    due = _today() + timedelta(days=due_in)
    warned_at = None if warned_ago is None else _today() - timedelta(days=warned_ago)
    meter_id = await _meter(bot_session, flat_id, due=due, warned_at=warned_at)

    await _run(task_broker, warn_verification)
    await _run(task_broker, warn_verification)

    [text] = _texts(bot_broker, user_id)
    assert expected.format(due=due) in text
    assert await _warned_at(bot_session, meter_id) == _today()


async def _appointment(
    session: AsyncSession,
    house_id: HouseId,
    user_id: UserId,
    day: date,
    status: AppointmentStatus = AppointmentStatus.BOOKED,
) -> None:
    house = await HousesRepo(session).get(house_id)
    assert house is not None
    assert house.org_id is not None
    session.add(
        Appointment(
            org_id=house.org_id,
            house_id=house_id,
            user_id=user_id,
            starts_at=datetime.combine(day, time(10), tzinfo=UTC),
            status=status,
        )
    )
    await session.commit()


def _to_user(bot_broker: RecordingBroker, user_id: UserId) -> list[dict[str, Any]]:
    return [
        kwargs
        for kwargs in bot_broker.enqueued(TaskName.SEND_TO_USER)
        if kwargs["user_id"] == user_id
    ]


@pytest.mark.parametrize(
    ("days_ahead", "status", "reminded"),
    [
        (1, AppointmentStatus.BOOKED, True),
        (2, AppointmentStatus.BOOKED, False),
        (1, AppointmentStatus.CANCELLED, False),
    ],
)
async def test_only_tomorrows_appointment_is_reminded_once(
    bot_session: AsyncSession,
    task_broker: InMemoryBroker,
    bot_broker: RecordingBroker,
    days_ahead: int,
    status: AppointmentStatus,
    reminded: bool,
) -> None:
    house_id = await _house(bot_session)
    _, user_id = await _resident(bot_session, house_id)
    await _appointment(
        bot_session, house_id, user_id, _today() + timedelta(days=days_ahead), status
    )

    await _run(task_broker, remind_appointments)
    await _run(task_broker, remind_appointments)

    queued = _to_user(bot_broker, user_id)
    assert [kwargs["mandatory"] for kwargs in queued] == ([True] if reminded else [])


async def test_each_moment_of_each_window_is_reminded_once(
    session: AsyncSession, publisher: TaskPublisher, broker: RecordingBroker
) -> None:
    # отметка различает период и момент: открытие не глушит напоминание о
    # закрытии, а сентябрь - октябрь. Дни фиксированы, поэтому сервис
    # вызывается напрямую, мимо задачи с ее datetime.now
    house_id = await _house(
        session, {"meter_window_day_from": 15, "meter_window_day_to": 25}
    )
    flat_id, user_id = await _resident(session, house_id)
    await _meter(session, flat_id)
    service = _service(session, publisher)

    for day in (date(2026, 9, 15), date(2026, 9, 23), date(2026, 10, 15)):
        await service.remind_readings(day)
        await service.remind_readings(day)
    await publisher.flush()

    assert len(_to_users(broker, user_id)) == 3


def _service(session: AsyncSession, publisher: TaskPublisher) -> RemindersService:
    return RemindersService(
        HousesRepo(session),
        MetersRepo(session),
        ResidentsRepo(session),
        PollsRepo(session),
        ChatsRepo(session),
        ReceptionRepo(session),
        EventsRepo(session),
        EventsService(EventsRepo(session)),
        make_notifications_service(session, publisher),
    )


async def _wrapping(
    session: AsyncSession, day_from: int, day_to: int, submitted_for: date
) -> UserId:
    house_id = await _house(
        session, {"meter_window_day_from": day_from, "meter_window_day_to": day_to}
    )
    flat_id, user_id = await _resident(session, house_id)
    await _submitted(session, await _meter(session, flat_id), user_id, submitted_for)
    return user_id


async def test_a_reading_from_the_head_of_a_wrapping_window_closes_it(
    session: AsyncSession, publisher: TaskPublisher, broker: RecordingBroker
) -> None:
    # окно 25-5, сдано 27 сентября: 3 октября закрывается то же окно
    user_id = await _wrapping(session, 25, 5, date(2026, 9, 1))

    await _service(session, publisher).remind_readings(date(2026, 10, 3))
    await publisher.flush()

    assert _to_users(broker, user_id) == []


async def test_a_reading_from_the_tail_of_a_wrapping_window_leaves_the_next_open(
    session: AsyncSession, publisher: TaskPublisher, broker: RecordingBroker
) -> None:
    # окно 25-1, сдано 1 октября за сентябрь: октябрьское окно ждет своих
    user_id = await _wrapping(session, 25, 1, date(2026, 9, 1))
    service = _service(session, publisher)

    await service.remind_readings(date(2026, 10, 25))
    await service.remind_readings(date(2026, 10, 30))
    await publisher.flush()

    assert len(_to_users(broker, user_id)) == 2


async def test_a_resident_of_two_houses_gets_each_window_of_each(
    session: AsyncSession, publisher: TaskPublisher, broker: RecordingBroker
) -> None:
    first = await _house(
        session, {"meter_window_day_from": 15, "meter_window_day_to": 25}
    )
    second = await _house(
        session, {"meter_window_day_from": 20, "meter_window_day_to": 28}
    )
    first_flat, user_id = await _resident(session, first)
    second_flat, _ = await _resident(session, second, user_id=user_id)
    await _meter(session, first_flat)
    await _meter(session, second_flat)
    service = _service(session, publisher)

    await service.remind_readings(date(2026, 9, 15))
    await service.remind_readings(date(2026, 9, 20))
    await publisher.flush()

    assert len(_to_users(broker, user_id)) == 2


async def _stamps(session: AsyncSession, user_id: UserId) -> int:
    stmt = select(func.count()).where(
        events_table.c.type == EventType.READING_REMINDER_SENT,
        events_table.c.user_id == user_id,
    )
    count: int = (await session.execute(stmt)).scalar_one()
    return count


async def test_windows_opening_the_same_day_send_one_text_and_stamp_both(
    session: AsyncSession, publisher: TaskPublisher, broker: RecordingBroker
) -> None:
    window = {"meter_window_day_from": 15, "meter_window_day_to": 25}
    first = await _house(session, window)
    second = await _house(session, window)
    first_flat, user_id = await _resident(session, first)
    second_flat, _ = await _resident(session, second, user_id=user_id)
    await _meter(session, first_flat)
    await _meter(session, second_flat)

    await _service(session, publisher).remind_readings(date(2026, 9, 15))
    await publisher.flush()

    assert len(_to_users(broker, user_id)) == 1
    assert await _stamps(session, user_id) == 2


async def test_a_house_without_an_org_gets_no_reading_reminder(
    session: AsyncSession, publisher: TaskPublisher, broker: RecordingBroker
) -> None:
    # без УК показания некому принять, хотя окно такого дома открыто всегда
    house_id = await _house(session)
    stmt = update(houses_table).where(houses_table.c.id == house_id).values(org_id=None)
    await session.execute(stmt)
    flat_id, user_id = await _resident(session, house_id)
    await _meter(session, flat_id)

    await _service(session, publisher).remind_readings(date(2026, 9, 1))
    await publisher.flush()

    assert _to_users(broker, user_id) == []


async def test_an_uncounted_vote_leaves_the_flat_reminded_but_not_the_voter(
    bot_session: AsyncSession, task_broker: InMemoryBroker, bot_broker: RecordingBroker
) -> None:
    # голос неподтвержденного совладельца в кворум не идет: подтвержденный
    # владелец той же квартиры получает напоминание, сам совладелец - нет
    house_id = await _house(bot_session)
    flat_id, owner = await _resident(bot_session, house_id)
    _, co_owner = await _resident(
        bot_session, house_id, flat_id=flat_id, verified=False
    )
    poll_id = await _poll(bot_session, house_id, timedelta(hours=24))
    await _vote(bot_session, poll_id, flat_id, co_owner, counted=False)

    await _run(task_broker, remind_polls)

    assert _to_users(bot_broker, owner)
    assert _to_users(bot_broker, co_owner) == []
