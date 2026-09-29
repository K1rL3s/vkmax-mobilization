import json
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    add_meter,
    add_reading,
    add_resident,
    add_user,
    empty_bot_setup,
    make_bot_config,
)
from tests.test_auth import signed_init_data
from tests.test_requests import _add_group

from zheka.api.app import app_factory
from zheka.core.enums import (
    AppointmentStatus,
    ChatStatus,
    HouseState,
    MapPeriod,
    OrgRole,
    RequestCategory,
    RequestChannel,
    RequestStatus,
    VerificationStatus,
)
from zheka.core.ids import FlatId, HouseId, MaxChatId, MaxUserId, OrgId, RequestGroupId
from zheka.core.services.admin_map import (
    AdminMapData,
    AdminMapFilters,
    AdminMapRow,
    AdminMapService,
)
from zheka.core.services.readings import current_period
from zheka.infra.database.models import (
    Announcement,
    Appointment,
    Chat,
    Flat,
    House,
    OrgMember,
    Organization,
    Request,
    User,
    VerificationRequest,
)
from zheka.infra.database.repos.admin_map import AdminMapRepo, RequestCounts
from zheka.infra.database.repos.analytics import AnalyticsRepo, SeasonCount
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

NOW = datetime(2031, 3, 12, 12, tzinfo=UTC)


def _new_org(timezone: str) -> Organization:
    return Organization(
        timezone=timezone,
        name=f"УК Карта {secrets.token_hex(4)}",
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Картографическая область, Картоград, Полярная, 1",
        registered_at=NOW - timedelta(days=365),
    )


async def _org(session: AsyncSession, timezone: str = "Europe/Moscow") -> OrgId:
    org = _new_org(timezone)
    session.add(org)
    await session.flush()
    return org.id


async def _house(
    session: AsyncSession,
    org_id: OrgId,
    *,
    located: bool = True,
    timezone: str = "Europe/Moscow",
) -> HouseId:
    house = House(
        timezone=timezone,
        org_id=org_id,
        region="Картографическая область",
        city="Картоград",
        street="Полярная",
        building=secrets.token_hex(2),
        cadastral_no=secrets.token_hex(8),
        chat_binding_code=secrets.token_hex(4),
        lat=Decimal("55.750000") if located else None,
        lon=Decimal("37.620000") if located else None,
    )
    session.add(house)
    await session.flush()
    return house.id


async def _flat(session: AsyncSession, house_id: HouseId) -> FlatId:
    flat = Flat(house_id=house_id, number=secrets.token_hex(3))
    session.add(flat)
    await session.flush()
    return flat.id


async def _request(
    session: AsyncSession,
    house_id: HouseId,
    *,
    status: RequestStatus = RequestStatus.NEW,
    category: RequestCategory = RequestCategory.ELEVATOR,
    created_at: datetime = NOW - timedelta(hours=1),
    deadline_at: datetime = NOW + timedelta(days=1),
    escalated_at: datetime | None = None,
    rating: int | None = None,
    group_id: RequestGroupId | None = None,
) -> None:
    session.add(
        Request(
            house_id=house_id,
            category=category,
            description="Заявка",
            status=status,
            channel=RequestChannel.MINIAPP,
            created_at=created_at,
            deadline_at=deadline_at,
            escalated_at=escalated_at,
            rating=rating,
            group_id=group_id,
        ),
    )
    await session.flush()


async def _announce(
    session: AsyncSession,
    org_id: OrgId,
    house_id: HouseId,
    created_at: datetime,
    text: str = "Отключение воды",
    *,
    urgent: bool = True,
) -> None:
    session.add(
        Announcement(
            org_id=org_id,
            house_ids=[house_id],
            text=text,
            channels=["direct"],
            created_by=await add_user(session),
            urgent=urgent,
            created_at=created_at,
        ),
    )
    await session.flush()


async def _map(
    session: AsyncSession,
    org_id: OrgId,
    *,
    can_manage: bool = True,
    **filters: Any,
) -> AdminMapData:
    service = AdminMapService(
        HousesRepo(session),
        ResidentsRepo(session),
        AdminMapRepo(session),
        AnalyticsRepo(session),
        OrgsRepo(session),
    )
    return await service.houses(org_id, can_manage, AdminMapFilters(**filters), NOW)


def _by_house(data: AdminMapData) -> dict[HouseId, AdminMapRow]:
    return {row.house.id: row for row in data.items}


async def test_each_house_state_follows_its_worst_request(
    session: AsyncSession,
) -> None:
    org_id = await _org(session)
    emergency, escalated, overdue, open_, calm = [
        await _house(session, org_id) for _ in range(5)
    ]
    late = NOW - timedelta(hours=1)
    complained = NOW - timedelta(minutes=30)
    await _request(session, emergency, category=RequestCategory.LEAK)
    await _request(session, emergency, deadline_at=late, escalated_at=complained)
    await _request(session, escalated, deadline_at=late, escalated_at=complained)
    await _request(session, escalated, deadline_at=late)
    await _request(session, overdue, deadline_at=late)
    await _request(session, overdue, group_id=await _add_group(session, overdue))
    await _request(session, open_)
    await _request(
        session,
        calm,
        status=RequestStatus.DONE,
        category=RequestCategory.LEAK,
        escalated_at=complained,
        group_id=await _add_group(session, calm),
    )

    rows = _by_house(await _map(session, org_id))

    assert {house: row.counts.state for house, row in rows.items()} == {
        emergency: HouseState.EMERGENCY,
        escalated: HouseState.ESCALATED,
        overdue: HouseState.OVERDUE,
        open_: HouseState.OPEN,
        calm: HouseState.CALM,
    }
    assert {house: row.counts for house, row in rows.items()} == {
        emergency: RequestCounts(
            open=2,
            overdue=1,
            escalated=1,
            emergency=1,
            period_requests=2,
        ),
        escalated: RequestCounts(open=2, overdue=2, escalated=1, period_requests=2),
        overdue: RequestCounts(open=2, overdue=1, grouped=1, period_requests=2),
        open_: RequestCounts(open=1, period_requests=1),
        calm: RequestCounts(period_requests=1),
    }


async def test_an_open_leak_paints_the_house_red_even_before_its_deadline(
    session: AsyncSession,
) -> None:
    org_id = await _org(session)
    house_id = await _house(session, org_id)
    await _request(session, house_id, category=RequestCategory.LEAK)

    row = _by_house(await _map(session, org_id))[house_id]

    assert (row.counts.state, row.counts.emergency, row.counts.overdue) == (
        HouseState.EMERGENCY,
        1,
        0,
    )


async def test_states_filter_keeps_only_the_asked_states(
    session: AsyncSession,
) -> None:
    org_id = await _org(session)
    red, calm = await _house(session, org_id), await _house(session, org_id)
    await _request(session, red, deadline_at=NOW - timedelta(hours=1))

    data = await _map(session, org_id, states=frozenset({HouseState.CALM}))

    assert [row.house.id for row in data.items] == [calm]


async def test_category_narrows_the_counts(session: AsyncSession) -> None:
    org_id = await _org(session)
    house_id = await _house(session, org_id)
    await _request(session, house_id, category=RequestCategory.LEAK)
    await _request(session, house_id, category=RequestCategory.ELEVATOR)

    row = _by_house(
        await _map(session, org_id, category=RequestCategory.ELEVATOR),
    )[house_id]

    assert (row.counts.open, row.counts.emergency, row.counts.state) == (
        1,
        0,
        HouseState.OPEN,
    )


async def test_period_counts_requests_and_rating_inside_it(
    session: AsyncSession,
) -> None:
    org_id = await _org(session)
    house_id = await _house(session, org_id)
    for days, rating in ((5, 5), (20, 3), (100, 1)):
        await _request(
            session,
            house_id,
            status=RequestStatus.DONE,
            created_at=NOW - timedelta(days=days),
            rating=rating,
        )
    await _request(session, house_id, created_at=NOW - timedelta(days=100))

    week = _by_house(await _map(session, org_id, period=MapPeriod.WEEK))[house_id]
    month = _by_house(await _map(session, org_id, period=MapPeriod.MONTH))[house_id]

    assert (week.counts.period_requests, week.counts.rating) == (1, 500)
    assert (month.counts.period_requests, month.counts.rating) == (2, 400)


async def test_a_fresh_urgent_announcement_counts_and_an_old_one_does_not(
    session: AsyncSession,
) -> None:
    org_id = await _org(session)
    fresh, old = await _house(session, org_id), await _house(session, org_id)
    await _announce(session, org_id, fresh, NOW - timedelta(days=2), "Раньше")
    await _announce(session, org_id, fresh, NOW - timedelta(days=1), "Свежее")
    await _announce(
        session,
        org_id,
        fresh,
        NOW - timedelta(hours=1),
        "Обычное",
        urgent=False,
    )
    await _announce(session, org_id, old, NOW - timedelta(days=4))

    rows = _by_house(await _map(session, org_id))

    assert {
        house: None if row.urgent is None else row.urgent.text
        for house, row in rows.items()
    } == {fresh: "Свежее", old: None}


async def test_urgent_filter_keeps_houses_with_an_urgent_announcement(
    session: AsyncSession,
) -> None:
    org_id = await _org(session)
    urgent, _quiet = await _house(session, org_id), await _house(session, org_id)
    await _announce(session, org_id, urgent, NOW - timedelta(hours=3))

    data = await _map(session, org_id, urgent=True)

    assert [row.house.id for row in data.items] == [urgent]


async def test_an_active_poll_shows_with_its_turnout(session: AsyncSession) -> None:
    org_id = await _org(session)
    house_id, _quiet = await _house(session, org_id), await _house(session, org_id)
    flats = [await _flat(session, house_id) for _ in range(4)]
    author = await add_user(session)
    polls = PollsRepo(session)
    soon, _later, closed, _expired = [
        await polls.create(
            house_id,
            org_id,
            author,
            "admin",
            title,
            None,
            False,
            NOW - timedelta(days=3),
            NOW + ends_in,
            ["За", "Против"],
        )
        for title, ends_in in (
            ("Ремонт крыши", timedelta(days=2)),
            ("Покраска", timedelta(days=5)),
            ("Закрытый", timedelta(days=1)),
            ("Истекший", -timedelta(hours=1)),
        )
    ]
    await polls.close(closed)
    option = (await polls.list_options(soon.id))[0]
    voter = await add_user(session)
    resident = await add_resident(session, voter, house_id, flats[0])
    await polls.add_vote(
        soon.id,
        [option.id],
        voter,
        resident.id,
        flats[0],
        counted_by_area=True,
    )

    rows = _by_house(await _map(session, org_id, poll=True))
    row = rows[house_id]

    assert list(rows) == [house_id]
    assert row.poll is not None
    assert (row.poll.poll_id, row.poll.voted_flats, row.poll_turnout) == (
        soon.id,
        1,
        2500,
    )


async def test_appointments_today_follow_the_org_time_zone(
    session: AsyncSession,
) -> None:
    org_id = await _org(session, "Asia/Vladivostok")
    house_id = await _house(session, org_id, timezone="Europe/Moscow")
    await _house(session, org_id)
    user_id = await add_user(session)
    late_tonight = datetime(2031, 3, 12, 23, 30, tzinfo=UTC) - timedelta(hours=10)
    for starts_at, status in (
        (late_tonight, AppointmentStatus.BOOKED),
        (late_tonight - timedelta(hours=1), AppointmentStatus.CANCELLED),
        (late_tonight - timedelta(days=1), AppointmentStatus.BOOKED),
        (late_tonight + timedelta(hours=1), AppointmentStatus.BOOKED),
    ):
        session.add(
            Appointment(
                org_id=org_id,
                house_id=house_id,
                user_id=user_id,
                starts_at=starts_at,
                status=status,
            ),
        )
    await session.flush()

    data = await _map(session, org_id, reception_today=True)

    assert [(row.house.id, row.appointments_today) for row in data.items] == [
        (house_id, 1),
    ]


async def test_meters_below_keeps_houses_under_the_share(
    session: AsyncSession,
) -> None:
    org_id = await _org(session)
    done, behind, _no_meters = [await _house(session, org_id) for _ in range(3)]
    user_id = await add_user(session)
    for house_id in (done, behind):
        meter_id = await add_meter(session, await _flat(session, house_id))
        if house_id == done:
            await add_reading(
                session,
                meter_id,
                current_period(NOW.date()),
                1000,
                user_id,
            )

    data = await _map(session, org_id, meters_below=50)

    assert [(row.house.id, row.meters) for row in data.items] == [
        (behind, SeasonCount(flats_total=1, submitted=0, percent=0)),
    ]


async def _verification(
    session: AsyncSession,
    house_id: HouseId,
    status: VerificationStatus = VerificationStatus.PENDING,
) -> None:
    session.add(
        VerificationRequest(
            flat_id=await _flat(session, house_id),
            user_id=await add_user(session),
            account_no="000001",
            status=status,
        ),
    )
    await session.flush()


async def test_an_employee_gets_no_resident_fields_and_no_pending_filter(
    session: AsyncSession,
) -> None:
    org_id = await _org(session)
    pending, quiet = await _house(session, org_id), await _house(session, org_id)
    await _verification(session, pending)

    data = await _map(session, org_id, can_manage=False, pending=True)

    assert {
        row.house.id: (
            row.flats_count,
            row.residents_count,
            row.verified_residents,
            row.pending_verifications,
            row.chat_bound,
        )
        for row in data.items
    } == {
        pending: (1, None, None, None, None),
        quiet: (0, None, None, None, None),
    }


async def test_an_admin_gets_resident_fields_and_the_pending_filter(
    session: AsyncSession,
) -> None:
    org_id = await _org(session)
    pending, rejected = await _house(session, org_id), await _house(session, org_id)
    await _verification(session, pending)
    await _verification(session, rejected, VerificationStatus.REJECTED)
    flat_id = await _flat(session, pending)
    await add_resident(session, await add_user(session), pending, flat_id)
    await add_resident(
        session,
        await add_user(session),
        pending,
        flat_id,
        verified=False,
    )
    await _bind_chat(session, pending)

    data = await _map(session, org_id, pending=True)

    assert [
        (
            row.house.id,
            row.flats_count,
            row.residents_count,
            row.verified_residents,
            row.pending_verifications,
            row.chat_bound,
        )
        for row in data.items
    ] == [(pending, 2, 2, 1, 1, True)]


async def test_a_house_without_coordinates_is_only_counted(
    session: AsyncSession,
) -> None:
    org_id = await _org(session)
    located = await _house(session, org_id)
    await _house(session, org_id, located=False)
    await _house(session, org_id, located=False)

    data = await _map(session, org_id)

    assert ([row.house.id for row in data.items], data.without_coords) == (
        [located],
        2,
    )


async def test_another_orgs_houses_never_show(session: AsyncSession) -> None:
    org_id, other_id = await _org(session), await _org(session)
    own = await _house(session, org_id)
    foreign = await _house(session, other_id)
    await _request(session, foreign, deadline_at=NOW - timedelta(hours=1))
    await _announce(session, other_id, foreign, NOW - timedelta(hours=1))
    await _announce(session, other_id, own, NOW - timedelta(hours=1))

    data = await _map(session, org_id)

    assert [(row.house.id, row.urgent) for row in data.items] == [(own, None)]
    assert data.without_coords == 0


async def _staff_headers(
    session: AsyncSession,
    org_id: OrgId,
    role: OrgRole,
) -> dict[str, str]:
    max_user_id = MaxUserId(secrets.randbits(40))
    user = User(max_user_id=max_user_id, name="Сотрудник")
    session.add(user)
    await session.flush()
    session.add(OrgMember(org_id=org_id, user_id=user.id, role=role))
    await session.flush()
    init_data = signed_init_data(
        datetime.now(UTC),
        user=json.dumps({"id": max_user_id, "first_name": "Сотрудник"}),
    )
    return {"WebAppData": init_data}


async def test_only_an_admin_sees_resident_fields_in_the_list_and_on_the_map(
    bot_session: AsyncSession,
) -> None:
    org_id = await _org(bot_session)
    house_id = await _house(bot_session, org_id)
    await _flat(bot_session, house_id)
    await _bind_chat(bot_session, house_id)
    headers = {
        role: await _staff_headers(bot_session, org_id, role)
        for role in (OrgRole.EMPLOYEE, OrgRole.ADMIN)
    }
    await bot_session.commit()
    app = app_factory(make_bot_config(), empty_bot_setup())

    seen = {}
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        for role, role_headers in headers.items():
            houses = await client.get("/api/admin/houses", headers=role_headers)
            admin_map = await client.get(
                "/api/admin/map/houses",
                headers=role_headers,
                params={"states": ["overdue", "calm"], "period": "week"},
            )
            listed, mapped = houses.json()["items"][0], admin_map.json()["items"][0]
            seen[role] = (
                houses.status_code,
                admin_map.status_code,
                [
                    listed[key]
                    for key in ("flats_count", "residents_count", "chat_bound")
                ],
                [
                    mapped[key]
                    for key in (
                        "flats_count",
                        "residents_count",
                        "verified_residents",
                        "pending_verifications",
                        "chat_bound",
                    )
                ],
            )

    assert seen == {
        OrgRole.EMPLOYEE: (200, 200, [1, None, True], [1, None, None, None, None]),
        OrgRole.ADMIN: (200, 200, [1, 0, True], [1, 0, 0, 0, True]),
    }


async def test_a_request_on_review_neither_escalates_nor_alarms(
    session: AsyncSession,
) -> None:
    org_id = await _org(session)
    complained, leaked = await _house(session, org_id), await _house(session, org_id)
    for house_id, category in (
        (complained, RequestCategory.ELEVATOR),
        (leaked, RequestCategory.LEAK),
    ):
        await _request(
            session,
            house_id,
            status=RequestStatus.ON_REVIEW,
            category=category,
            deadline_at=NOW - timedelta(hours=1),
            escalated_at=NOW - timedelta(minutes=30),
        )

    rows = _by_house(await _map(session, org_id))

    assert {house: row.counts for house, row in rows.items()} == {
        complained: RequestCounts(open=1, period_requests=1),
        leaked: RequestCounts(open=1, period_requests=1),
    }
    assert {row.counts.state for row in rows.values()} == {HouseState.OPEN}


async def _bind_chat(session: AsyncSession, house_id: HouseId) -> None:
    session.add(
        Chat(
            chat_id=MaxChatId(secrets.randbits(48)),
            house_id=house_id,
            title="Дом",
            bound_at=NOW,
            status=ChatStatus.ACTIVE,
        ),
    )
    await session.flush()
