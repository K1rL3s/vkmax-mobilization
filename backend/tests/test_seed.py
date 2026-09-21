import csv
import secrets
import tempfile
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from tests.conftest import make_config
from tests.test_analytics import _service as analytics_service
from tests.test_charges import _make_service as charges_service

from zheka.core.charges import parse_lines
from zheka.core.enums import RequestStatus
from zheka.core.errors import EntityNotFound, NotEnoughRights
from zheka.core.ids import FlatId, MaxUserId, OrgId, UserId
from zheka.core.services.demo import DEMO_INN, DemoService, demo_flat_number
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.meter_access import MeterAccess
from zheka.core.services.readings import ReadingsService, current_period
from zheka.infra.database.models import Charge, User
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.base import metadata
from zheka.infra.database.tables.charges import charges_table
from zheka.infra.database.tables.houses import flats_table, houses_table
from zheka.infra.database.tables.organizations import (
    org_members_table,
    organizations_table,
)
from zheka.infra.database.tables.requests import (
    request_photos_table,
    requests_table,
)
from zheka.infra.database.tables.residents import residents_table
from zheka.infra.database.tables.users import users_table
from zheka.seed.demo import PROFILES, RESULT_PHOTOS, seed
from zheka.seed.directory import DATA_DIR

TODAY = date(2026, 9, 21)
NOW = datetime.combine(TODAY, time(), UTC)
FILES = Path(tempfile.gettempdir()) / "zheka-test-seed-files"


def _demo(session: AsyncSession) -> DemoService:
    return DemoService(
        OrgsRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        MetersRepo(session),
        ChargesRepo(session),
        UsersRepo(session),
    )


def _inn_is_valid(inn: str) -> bool:
    weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
    digits = [int(char) for char in inn]
    return (
        sum(w * d for w, d in zip(weights, digits, strict=False)) % 11 % 10 == digits[9]
    )


@pytest_asyncio.fixture(scope="module")
async def seeded(engine: AsyncEngine) -> AsyncGenerator[AsyncConnection]:
    # сид один на модуль: он долгий, а тесты читают его каждый в своей
    # точке сохранения, которую потом откатывают
    async with engine.connect() as conn:
        transaction = await conn.begin()
        async with AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
        ) as session:
            assert await seed(session, _demo(session), FILES, TODAY)
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
    return OrgId(org.id)


async def test_a_second_seed_changes_nothing(db: AsyncSession) -> None:
    before = await _counts(db)

    assert not await seed(db, _demo(db), FILES, TODAY)

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
    assert all(metric.platform_median is not None for metric in benchmark.metrics)
    assert benchmark.metrics
    assert any(row.city is not None for row in benchmark.regions)
    assert benchmark.unconnected_houses


async def test_the_five_organizations_rank_without_a_tie(db: AsyncSession) -> None:
    service = analytics_service(db)
    ranks = []
    for profile in PROFILES:
        org = await OrgsRepo(db).get_by_inn(profile.inn)
        assert org is not None
        benchmark = await service.benchmark(OrgId(org.id), NOW)
        ranks.append({metric.key: metric.rank for metric in benchmark.metrics})

    for key in ranks[0]:
        assert sorted(rank[key] or 0 for rank in ranks) == [1, 2, 3, 4, 5], key


async def test_every_seeded_user_is_unreachable(db: AsyncSession) -> None:
    rows = (
        await db.execute(select(users_table.c.max_user_id, users_table.c.max_chat_id))
    ).all()

    assert rows
    assert all(max_user_id < 0 for max_user_id, _chat in rows)
    assert all(chat is None for _max_user_id, chat in rows)


def test_every_fictional_inn_fails_the_checksum() -> None:
    assert not any(_inn_is_valid(profile.inn) for profile in PROFILES)


async def test_charge_lines_add_up_and_the_latest_breaks_down(db: AsyncSession) -> None:
    charges = (await db.execute(select(Charge))).scalars().all()
    assert charges
    for charge in charges:
        lines = parse_lines(charge.lines)
        assert sum(line.amount for line in lines) == charge.total
        # показание ниже прошлого не выставляется в минус
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
    # повышение тарифа приходится на последнюю квитанцию, ее открывают первой
    assert any(line.delta.tariff_effect for line in breakdown.lines)


async def _positive_user(session: AsyncSession, *, consent: bool = True) -> UserId:
    user = User(
        max_user_id=MaxUserId(secrets.randbits(40)),
        name="Проверяющий",
        consent_at=datetime.now(UTC) if consent else None,
    )
    session.add(user)
    await session.flush()
    return UserId(user.id)


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
    this_month = current_period(datetime.now(UTC).date())
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
        houses,
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
    # запись второй демо-организации ждала бы блокировки ИНН в транзакции
    # сида, поэтому дом отбирается у засеянной
    stmt = (
        update(houses_table)
        .where(houses_table.c.org_id == await _demo_org(db))
        .values(org_id=None)
    )
    await db.execute(stmt)

    with pytest.raises(EntityNotFound):
        await _demo(db).activate(await _positive_user(db))


async def test_no_seeded_request_waits_on_review(db: AsyncSession) -> None:
    # заявку на проверке закрыл бы планировщик и написал бы автору
    stmt = select(func.count()).where(
        requests_table.c.status == RequestStatus.ON_REVIEW
    )

    assert (await db.execute(stmt)).scalar_one() == 0


async def test_the_demo_window_is_open_all_month(db: AsyncSession) -> None:
    settings = await OrgsRepo(db).get_settings(await _demo_org(db))

    assert settings is not None
    assert settings.meter_window_always_open


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

    # засеянный счет кончается номером квартиры из цифр, а счет проверяющего
    # не кончается цифрами никогда, какой бы ни был его id
    assert all(number.isdigit() for number, _account in seeded)
    assert flat.account_no is not None
    assert not flat.account_no.rsplit("-", 1)[1].isdigit()
    assert flat.account_no not in {account for _number, account in seeded}


async def test_a_result_photo_shows_the_work_of_its_request(db: AsyncSession) -> None:
    stmt = select(request_photos_table.c.path, requests_table.c.category).join(
        requests_table,
        requests_table.c.id == request_photos_table.c.request_id,
    )
    rows = (await db.execute(stmt)).all()

    assert len(rows) == len(RESULT_PHOTOS)
    assert all(category in RESULT_PHOTOS[path] for path, category in rows)


async def test_a_real_manager_is_replaced_only_in_moscow(db: AsyncSession) -> None:
    # по карточке у дома есть настоящая УК: придуманная встает на ее место
    # только там, где домов без УК на улице не хватило
    with (DATA_DIR / "houses.csv").open(encoding="utf-8") as file:
        managed = {
            (row["city"], row["building"])
            for row in csv.DictReader(file)
            if row["org_inn"]
        }
    stmt = (
        select(houses_table.c.city, houses_table.c.building)
        .join(organizations_table, organizations_table.c.id == houses_table.c.org_id)
        .where(organizations_table.c.inn.in_([profile.inn for profile in PROFILES]))
    )
    taken = set((await db.execute(stmt)).tuples().all())

    replaced = {city for city, building in taken if (city, building) in managed}
    assert replaced == {"Москва"}
