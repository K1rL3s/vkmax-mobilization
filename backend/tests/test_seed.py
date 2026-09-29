import csv
import secrets
import tempfile
from collections.abc import AsyncGenerator, Sequence
from datetime import UTC, datetime, timedelta
from math import cos, radians
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Row, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from tests.conftest import alembic_config, make_config
from tests.test_analytics import _service as analytics_service
from tests.test_charges import _make_service as charges_service

from zheka.core.charges import parse_lines
from zheka.core.danger import detect_danger
from zheka.core.enums import (
    DangerKind,
    OrgRole,
    PollStatus,
    RequestCategory,
    RequestStatus,
)
from zheka.core.errors import EntityNotFound, NotEnoughRights
from zheka.core.ids import API_CHECKER_MAX_USER_ID, FlatId, MaxUserId, OrgId, UserId
from zheka.core.services.demo import (
    API_CHECKER_DEMO_NUMBER,
    CHECKER_RESERVED,
    DEMO_INN,
    DEMO_INNS,
    DemoService,
    demo_account_no,
    demo_flat_number,
)
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.houses import PUBLIC_STATS_MIN_CLOSED, PUBLIC_STATS_PERIOD
from zheka.core.services.meter_access import MeterAccess
from zheka.core.services.readings import ReadingsService, current_period
from zheka.infra.database.models import Charge, User
from zheka.infra.database.repos.analytics import AnalyticsRepo
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.announcements import announcements_table
from zheka.infra.database.tables.base import metadata
from zheka.infra.database.tables.charges import charges_table
from zheka.infra.database.tables.houses import flats_table, houses_table
from zheka.infra.database.tables.meters import meters_table, readings_table
from zheka.infra.database.tables.organizations import (
    org_members_table,
    organizations_table,
)
from zheka.infra.database.tables.polls import polls_table
from zheka.infra.database.tables.requests import (
    request_attachments_table,
    requests_table,
)
from zheka.infra.database.tables.residents import (
    flat_verification_requests_table,
    residents_table,
)
from zheka.infra.database.tables.users import users_table
from zheka.seed.demo import (
    ANNOUNCEMENTS,
    BACKGROUND_PROFILES,
    MAP_STATES,
    POLL_RESULTS,
    PROFILES,
    RESULT_PHOTOS,
    seed,
)
from zheka.seed.directory import DATA_DIR

NOW = datetime(2026, 9, 21, 20, 30, tzinfo=UTC)
TODAY = NOW.date()
FILES = Path(tempfile.gettempdir()) / "zheka-test-seed-files"
MAP_HOURS = (0, 6, 12, 24, 48, 71)
URGENT_ACTIVE = timedelta(days=3)
KM_PER_DEGREE = 111.2
TERRITORY_KM = 1.5


def _demo(session: AsyncSession) -> DemoService:
    return DemoService(
        OrgsRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        MetersRepo(session),
        ChargesRepo(session),
        UsersRepo(session),
    )


@pytest_asyncio.fixture(scope="module")
async def seeded(engine: AsyncEngine) -> AsyncGenerator[AsyncConnection]:
    async with engine.connect() as conn:
        transaction = await conn.begin()
        async with AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
        ) as session:
            assert await seed(session, _demo(session), FILES, NOW)
            await session.commit()
        yield conn
        await transaction.rollback()


@pytest_asyncio.fixture
async def db(seeded: AsyncConnection) -> AsyncGenerator[AsyncSession]:
    async with AsyncSession(
        bind=seeded,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session


async def _counts(session: AsyncSession) -> dict[str, int]:
    counts = {}
    for table in metadata.sorted_tables:
        stmt = select(func.count()).select_from(table)
        counts[table.name] = (await session.execute(stmt)).scalar_one()
    return counts


async def _demo_org(session: AsyncSession) -> OrgId:
    org = await OrgsRepo(session).get_by_inn(DEMO_INN)
    assert org is not None
    return org.id


async def test_a_second_seed_changes_nothing(db: AsyncSession) -> None:
    before = await _counts(db)

    assert not await seed(db, _demo(db), FILES, NOW)

    assert await _counts(db) == before
    assert before["requests"] > 0


async def test_the_dashboard_and_the_benchmark_are_not_empty(db: AsyncSession) -> None:
    org_id = await _demo_org(db)
    service = analytics_service(db)

    dashboard = await service.dashboard(org_id, None, None, None, NOW)
    benchmark = await service.benchmark(org_id, NOW)

    assert not dashboard.is_empty
    tiles = {tile.key: tile.value for tile in dashboard.tiles}
    assert tiles["overdue"] > 0
    weeks = next(chart for chart in dashboard.charts if chart.key == "by_week")
    assert sum(point.value for point in weeks.points) > 0
    assert benchmark.metrics
    assert any(row.city is not None for row in benchmark.regions)
    assert benchmark.unconnected_houses


async def test_the_five_organizations_rank_without_a_tie(db: AsyncSession) -> None:
    service = analytics_service(db)
    ranks = []
    for profile in PROFILES:
        org = await OrgsRepo(db).get_by_inn(profile.inn)
        assert org is not None
        benchmark = await service.benchmark(org.id, NOW)
        ranks.append({metric.key: metric.rank for metric in benchmark.metrics})

    for key in ranks[0]:
        assert None not in {rank[key] for rank in ranks}, key
        assert len({rank[key] for rank in ranks}) == len(PROFILES), key


async def test_every_seeded_user_is_unreachable(db: AsyncSession) -> None:
    rows = (
        await db.execute(select(users_table.c.max_user_id, users_table.c.max_chat_id))
    ).all()

    assert rows
    assert all(max_user_id < 0 for max_user_id, _chat in rows)
    assert all(chat is None for _max_user_id, chat in rows)


def test_every_fictional_inn_fails_the_checksum() -> None:
    weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
    for profile in (*PROFILES, *BACKGROUND_PROFILES):
        digits = [int(char) for char in profile.inn]
        checksum = sum(w * d for w, d in zip(weights, digits, strict=False)) % 11 % 10
        assert checksum != digits[9], profile.inn


async def test_charge_lines_add_up_and_the_latest_breaks_down(db: AsyncSession) -> None:
    charges = (await db.execute(select(Charge))).scalars().all()
    assert charges
    for charge in charges:
        lines = parse_lines(charge.lines)
        assert sum(line.amount for line in lines) == charge.total
        assert all(line.amount >= 0 for line in lines)

    latest = max(charges, key=lambda charge: charge.period)
    stmt = select(residents_table.c.user_id).where(
        residents_table.c.flat_id == latest.flat_id,
        residents_table.c.can_see_charges.is_(True),
    )
    owner = (await db.execute(stmt)).scalars().first()
    assert owner is not None

    breakdown = await charges_service(db).breakdown(latest.id, UserId(owner))

    assert breakdown.previous_charge is not None
    assert any(line.delta.tariff_effect for line in breakdown.lines)


async def _positive_user(session: AsyncSession, *, consent: bool = True) -> UserId:
    user = User(
        max_user_id=MaxUserId(secrets.randbits(40)),
        name="Проверяющий",
        consent_at=datetime.now(UTC) if consent else None,
    )
    session.add(user)
    await session.flush()
    return user.id


async def test_activation_twice_is_one_flat_and_the_month_is_open(
    db: AsyncSession,
) -> None:
    user_id = await _positive_user(db)
    demo = _demo(db)

    first = await demo.activate(user_id)
    verified_at = first.residency.resident.verified_at
    second = await demo.activate(user_id)

    assert first.residency.resident.id == second.residency.resident.id
    members = (
        select(func.count())
        .select_from(org_members_table)
        .where(org_members_table.c.user_id == user_id)
    )
    residents = (
        select(func.count())
        .select_from(residents_table)
        .where(residents_table.c.user_id == user_id)
    )
    flats = (
        select(func.count())
        .select_from(flats_table)
        .where(flats_table.c.number == demo_flat_number(user_id))
    )
    assert (await db.execute(members)).scalar_one() == 1
    assert (await db.execute(residents)).scalar_one() == 1
    assert (await db.execute(flats)).scalar_one() == 1
    assert verified_at is not None
    assert second.residency.resident.verified_at == verified_at

    flat_id = FlatId(second.residency.resident.flat_id or 0)
    this_month = current_period(datetime.now(ZoneInfo("Europe/Moscow")).date())
    charged = select(charges_table.c.period).where(charges_table.c.flat_id == flat_id)
    assert len((await db.execute(charged)).scalars().all()) == 6
    periods = await _readings(db).periods(flat_id)
    assert [(option.period, option.is_open) for option in periods.options] == [
        (this_month, True),
    ]
    assert this_month not in periods.submitted


def _readings(session: AsyncSession) -> ReadingsService:
    meters, houses, orgs = MetersRepo(session), HousesRepo(session), OrgsRepo(session)
    return ReadingsService(
        meters,
        ChargesRepo(session),
        orgs,
        MeterAccess(meters, houses, ResidentsRepo(session), orgs),
        FilesService(make_config().files, "test-token"),
        EventsService(EventsRepo(session)),
    )


async def test_activation_without_a_seed_is_not_found(session: AsyncSession) -> None:
    user_id = await _positive_user(session)

    with pytest.raises(EntityNotFound):
        await _demo(session).activate(user_id)


async def test_a_demo_organization_without_a_house_is_not_found(
    db: AsyncSession,
) -> None:
    stmt = (
        update(houses_table)
        .where(houses_table.c.org_id == await _demo_org(db))
        .values(org_id=None)
    )
    await db.execute(stmt)

    with pytest.raises(EntityNotFound):
        await _demo(db).activate(await _positive_user(db))


async def test_no_seeded_request_waits_on_review(db: AsyncSession) -> None:
    stmt = select(func.count()).where(
        requests_table.c.status == RequestStatus.ON_REVIEW,
    )

    assert (await db.execute(stmt)).scalar_one() == 0


async def test_every_demo_window_is_open_all_month(db: AsyncSession) -> None:
    for profile in PROFILES:
        org = await OrgsRepo(db).get_by_inn(profile.inn)
        assert org is not None
        settings = await OrgsRepo(db).get_settings(org.id)
        assert settings is not None
        assert settings.meter_window_always_open, profile.name


async def test_activation_without_consent_is_refused(db: AsyncSession) -> None:
    user_id = await _positive_user(db, consent=False)

    with pytest.raises(NotEnoughRights):
        await _demo(db).activate(user_id)


async def test_a_reviewer_account_never_equals_a_seeded_one(db: AsyncSession) -> None:
    access = await _demo(db).activate(await _positive_user(db))
    flat = access.residency.flat
    assert flat is not None
    stmt = select(flats_table.c.number, flats_table.c.account_no).where(
        flats_table.c.house_id == flat.house_id,
        flats_table.c.id != flat.id,
    )
    seeded = (await db.execute(stmt)).all()

    assert all(number.isdigit() for number, _account in seeded)
    assert flat.account_no is not None
    assert not flat.account_no.isdigit()
    assert flat.account_no not in {account for _number, account in seeded}


async def test_a_result_photo_shows_the_work_of_its_request(db: AsyncSession) -> None:
    stmt = select(request_attachments_table.c.path, requests_table.c.category).join(
        requests_table,
        requests_table.c.id == request_attachments_table.c.request_id,
    )
    rows = (await db.execute(stmt)).all()

    assert len(rows) == len(RESULT_PHOTOS)
    assert all(category in RESULT_PHOTOS[path] for path, category in rows)


async def test_no_real_manager_is_replaced(db: AsyncSession) -> None:
    with (DATA_DIR / "houses.csv").open(encoding="utf-8") as file:
        managed = {
            (row["city"], row["street"], row["building"])
            for row in csv.DictReader(file)
            if row["org_inn"]
        }
    stmt = (
        select(houses_table.c.city, houses_table.c.street, houses_table.c.building)
        .join(organizations_table, organizations_table.c.id == houses_table.c.org_id)
        .where(organizations_table.c.is_demo)
    )
    taken = set((await db.execute(stmt)).tuples().all())

    assert taken
    assert not taken & managed


async def test_a_flat_in_the_last_demo_organization_is_charged(
    db: AsyncSession,
) -> None:
    org, residency = await _demo(db).settle(await _checker(db), len(PROFILES))

    assert org.inn == PROFILES[-1].inn
    flat_id = FlatId(residency.resident.flat_id or 0)
    charged = select(charges_table.c.total).where(charges_table.c.flat_id == flat_id)
    totals = (await db.execute(charged)).scalars().all()
    assert len(totals) == 6
    assert all(total > 0 for total in totals)


async def test_the_mini_app_activation_keeps_a_demo_admin(db: AsyncSession) -> None:
    user_id = await _positive_user(db)
    await _demo(db).join(user_id, 1, OrgRole.ADMIN)

    access = await _demo(db).activate(user_id)

    assert access.membership.member.role is OrgRole.ADMIN


async def test_a_seeded_account_is_the_flat_number_padded_with_zeros(
    db: AsyncSession,
) -> None:
    stmt = select(flats_table.c.number, flats_table.c.account_no).where(
        flats_table.c.number == "12",
    )
    accounts = {account for _number, account in (await db.execute(stmt)).all()}

    assert accounts == {demo_account_no("12")} == {"0000000012"}


async def test_the_mini_app_activation_follows_the_link_number_and_role(
    db: AsyncSession,
) -> None:
    user_id = await _positive_user(db)

    access = await _demo(db).activate(user_id, 3, OrgRole.ADMIN)

    assert access.membership.org.inn == DEMO_INNS[2]
    assert access.membership.member.role is OrgRole.ADMIN
    assert access.residency.house.org_id == access.membership.org.id


async def test_a_reviewer_account_cannot_be_derived_from_the_flat(
    db: AsyncSession,
) -> None:
    access = await _demo(db).activate(await _positive_user(db))
    flat = access.residency.flat
    assert flat is not None

    assert flat.account_no != demo_account_no(flat.number)


async def test_the_checker_demo_organization_is_closed_to_everyone_else(
    db: AsyncSession,
) -> None:
    user_id = await _positive_user(db)
    demo = _demo(db)

    for attempt in (
        demo.activate(user_id, API_CHECKER_DEMO_NUMBER, OrgRole.ADMIN),
        demo.join(user_id, API_CHECKER_DEMO_NUMBER, OrgRole.ADMIN),
        demo.settle(user_id, API_CHECKER_DEMO_NUMBER),
    ):
        with pytest.raises(NotEnoughRights, match=CHECKER_RESERVED):
            await attempt

    access = await demo.activate(await _checker(db), API_CHECKER_DEMO_NUMBER)
    assert access.membership.org.inn == DEMO_INNS[API_CHECKER_DEMO_NUMBER - 1]


async def _checker(session: AsyncSession) -> UserId:
    user = User(
        max_user_id=API_CHECKER_MAX_USER_ID,
        name="Проверяющий API",
        consent_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()
    return user.id


async def test_the_mini_app_activation_returns_a_demo_executor_to_staff(
    db: AsyncSession,
) -> None:
    user_id = await _positive_user(db)
    await _demo(db).join(user_id, 1, OrgRole.EXECUTOR)

    access = await _demo(db).activate(user_id)

    assert access.membership.member.role is OrgRole.EMPLOYEE


async def test_no_seeded_deadline_is_due_at_the_seed(db: AsyncSession) -> None:
    assert await RequestsRepo(db).list_deadline_due(NOW) == []


async def test_only_demo_organizations_have_an_emergency_phone(
    db: AsyncSession,
) -> None:
    stmt = select(
        organizations_table.c.is_demo,
        organizations_table.c.emergency_phone.is_not(None),
    ).distinct()

    assert set((await db.execute(stmt)).tuples()) == {(True, True), (False, False)}


async def test_the_emergency_phone_migration_numbers_the_seeded_demo_orgs(
    seeded: AsyncConnection,
) -> None:
    migration = ScriptDirectory.from_config(alembic_config()).get_revision(
        "2c4883d34de8",
    )
    assert migration is not None

    def rerun(connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(connection)):
            migration.module.downgrade()
            migration.module.upgrade()

    stmt = select(
        organizations_table.c.inn,
        organizations_table.c.emergency_phone,
    ).where(organizations_table.c.emergency_phone.is_not(None))
    savepoint = await seeded.begin_nested()
    await seeded.run_sync(rerun)
    phones = dict((await seeded.execute(stmt)).tuples().all())
    await savepoint.rollback()

    assert phones == {
        profile.inn: f"+7 (000) 000-01-{number:02d}"
        for number, profile in enumerate(PROFILES, start=1)
    }


async def test_every_demo_organization_shows_its_own_stats(db: AsyncSession) -> None:
    seen = set()
    for profile in PROFILES:
        org = await OrgsRepo(db).get_by_inn(profile.inn)
        assert org is not None
        stats = await AnalyticsRepo(db).public_stats(
            org.id,
            NOW - PUBLIC_STATS_PERIOD,
            NOW,
        )
        assert stats.closed >= PUBLIC_STATS_MIN_CLOSED, profile.inn
        assert None not in (stats.on_time_share, stats.accept_time, stats.rating)
        seen.add((stats.on_time_share, stats.accept_time, stats.rating))

    assert len(seen) == len(PROFILES)


async def test_every_enterable_demo_org_has_twelve_houses_in_one_city(
    db: AsyncSession,
) -> None:
    for profile in PROFILES:
        org = await OrgsRepo(db).get_by_inn(profile.inn)
        assert org is not None
        houses = await HousesRepo(db).list_for_org(org.id)
        assert len(houses) == 12
        assert {house.city for house in houses} == {profile.city}
        assert all(house.lat is not None and house.lon is not None for house in houses)


async def test_each_city_has_at_least_five_demo_orgs(db: AsyncSession) -> None:
    rows = await db.execute(
        select(houses_table.c.city, func.count(func.distinct(houses_table.c.org_id)))
        .join(organizations_table, organizations_table.c.id == houses_table.c.org_id)
        .where(organizations_table.c.is_demo)
        .group_by(houses_table.c.city),
    )
    counts = dict(rows.tuples().all())
    assert counts.keys() == {"Москва", "Санкт-Петербург", "Казань"}
    assert all(count >= 5 for count in counts.values())


async def test_every_enterable_demo_org_shows_every_map_state(db: AsyncSession) -> None:
    for profile in PROFILES:
        org = await OrgsRepo(db).get_by_inn(profile.inn)
        assert org is not None
        houses = await HousesRepo(db).list_for_org(org.id)
        stmt = select(
            requests_table.c.house_id,
            requests_table.c.status,
            requests_table.c.category,
            requests_table.c.deadline_at,
            requests_table.c.escalated_at,
        ).where(requests_table.c.house_id.in_([house.id for house in houses]))
        rows = (await db.execute(stmt)).all()
        for hours in MAP_HOURS:
            now = NOW + timedelta(hours=hours)
            states = {
                _map_state([row for row in rows if row.house_id == house.id], now)
                for house in houses
            }
            assert states == set(MAP_STATES), (profile.name, hours)


async def test_every_enterable_demo_org_has_a_fresh_urgent_notice_and_a_poll(
    db: AsyncSession,
) -> None:
    for profile in PROFILES:
        org = await OrgsRepo(db).get_by_inn(profile.inn)
        assert org is not None
        urgent = select(announcements_table.c.created_at).where(
            announcements_table.c.org_id == org.id,
            announcements_table.c.urgent,
        )
        polls = select(polls_table.c.ends_at).where(
            polls_table.c.org_id == org.id,
            polls_table.c.status == PollStatus.ACTIVE,
        )
        created = (await db.execute(urgent)).scalars().all()
        ends = (await db.execute(polls)).scalars().all()
        for hours in MAP_HOURS:
            now = NOW + timedelta(hours=hours)
            assert any(now - URGENT_ACTIVE <= at <= now for at in created), (
                profile.name,
                hours,
            )
            assert any(at > now for at in ends), (profile.name, hours)


async def test_an_announcement_reaches_only_the_houses_it_is_about(
    db: AsyncSession,
) -> None:
    orgs = select(organizations_table.c.id).where(organizations_table.c.is_demo)
    for org_id in (await db.execute(orgs)).scalars().all():
        houses = {house.id for house in await HousesRepo(db).list_for_org(org_id)}
        stmt = select(
            announcements_table.c.text,
            announcements_table.c.house_ids,
        ).where(announcements_table.c.org_id == org_id)
        rows = (await db.execute(stmt)).all()
        texts = {text for _age, text, _urgent in ANNOUNCEMENTS}
        shared = [row for row in rows if row.text in texts]
        assert len(shared) == len(ANNOUNCEMENTS)
        assert all(set(row.house_ids) == houses for row in shared)

    stmt = select(announcements_table.c.house_ids).where(
        announcements_table.c.text == POLL_RESULTS[1],
    )
    noted = (await db.execute(stmt)).scalars().all()
    closed = select(polls_table.c.house_id).where(
        polls_table.c.status == PollStatus.CLOSED,
    )
    assert noted
    assert set().union(*noted) <= set((await db.execute(closed)).scalars().all())


async def test_every_demo_organization_is_a_compact_territory(
    db: AsyncSession,
) -> None:
    stmt = (
        select(houses_table.c.org_id, houses_table.c.lat, houses_table.c.lon)
        .join(organizations_table, organizations_table.c.id == houses_table.c.org_id)
        .where(organizations_table.c.is_demo)
    )
    points: dict[OrgId, list[tuple[float, float]]] = {}
    for org_id, lat, lon in (await db.execute(stmt)).tuples():
        points.setdefault(org_id, []).append((float(lat), float(lon)))

    assert len(points) == len(PROFILES) + len(BACKGROUND_PROFILES)
    for territory in points.values():
        lats = [lat for lat, _lon in territory]
        lons = [lon for _lat, lon in territory]
        scale = cos(radians(lats[0]))
        assert (max(lats) - min(lats)) * KM_PER_DEGREE < TERRITORY_KM
        assert (max(lons) - min(lons)) * KM_PER_DEGREE * scale < TERRITORY_KM


async def test_a_pending_verification_states_a_mistyped_account(
    db: AsyncSession,
) -> None:
    stmt = select(
        flat_verification_requests_table.c.account_no,
        flats_table.c.account_no,
    ).join(flats_table, flats_table.c.id == flat_verification_requests_table.c.flat_id)
    rows = (await db.execute(stmt)).tuples().all()

    assert rows
    assert all(stated != real for stated, real in rows)


async def test_every_demo_house_has_readings_this_month(db: AsyncSession) -> None:
    submitted = (
        select(flats_table.c.house_id)
        .join(meters_table, meters_table.c.flat_id == flats_table.c.id)
        .join(readings_table, readings_table.c.meter_id == meters_table.c.id)
        .where(readings_table.c.period == current_period(TODAY))
    )
    stmt = (
        select(func.count())
        .select_from(houses_table)
        .join(organizations_table, organizations_table.c.id == houses_table.c.org_id)
        .where(
            organizations_table.c.is_demo,
            houses_table.c.id.not_in(submitted),
        )
    )

    assert (await db.execute(stmt)).scalar_one() == 0


def _map_state(rows: Sequence[Row[Any]], now: datetime) -> str:
    active = [
        row
        for row in rows
        if row.status not in {RequestStatus.DONE, RequestStatus.ON_REVIEW}
    ]
    overdue = [row for row in active if row.deadline_at < now]
    if any(row.category is RequestCategory.LEAK for row in active):
        return "emergency"
    if any(row.escalated_at is not None for row in overdue):
        return "escalated"
    if overdue:
        return "overdue"
    if any(row.status is not RequestStatus.DONE for row in rows):
        return "open"
    return "calm"


async def test_a_seeded_sparking_socket_is_marked_dangerous(db: AsyncSession) -> None:
    stmt = select(requests_table.c.description, requests_table.c.danger).distinct()

    marks = dict((await db.execute(stmt)).tuples().all())

    assert marks["Искрит розетка в щитке на этаже"] == DangerKind.ELECTRIC
    assert marks["Течет стояк в санузле"] is None


async def test_every_seeded_request_is_marked_by_its_own_words(
    db: AsyncSession,
) -> None:
    stmt = select(requests_table.c.description, requests_table.c.danger).distinct()

    marks = set((await db.execute(stmt)).tuples().all())

    assert marks == {
        (description, None if found is None else found.kind)
        for description, _ in marks
        for found in [detect_danger(description)]
    }
