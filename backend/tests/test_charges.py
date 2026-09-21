from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser, make_config, make_notifications_service

from zheka.core.enums import (
    EventType,
    MeterType,
    RequestCategory,
    ResidentRole,
    ServiceType,
    TariffZone,
)
from zheka.core.errors import EntityNotFound, InvalidState, NotEnoughRights
from zheka.core.ids import FlatId, HouseId, UserId
from zheka.core.services.charges import ChargesService
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.meter_access import MeterAccess
from zheka.core.services.readings import ReadingsService
from zheka.core.services.request_groups import GroupingService
from zheka.core.services.requests import RequestsService
from zheka.infra.database.models import Charge, Event, Resident, Tariff
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.events import events_table
from zheka.infra.yandex import YandexClassifier

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


def _make_service(session: AsyncSession) -> ChargesService:
    meters_repo = MetersRepo(session)
    houses_repo = HousesRepo(session)
    residents_repo = ResidentsRepo(session)
    orgs_repo = OrgsRepo(session)
    events = EventsService(EventsRepo(session))
    access = MeterAccess(meters_repo, houses_repo, residents_repo, orgs_repo)
    files_service = FilesService(make_config().files, "test-token")
    readings_service = ReadingsService(
        meters_repo,
        ChargesRepo(session),
        houses_repo,
        orgs_repo,
        access,
        files_service,
        events,
    )
    requests_repo = RequestsRepo(session)
    requests_service = RequestsService(
        requests_repo,
        houses_repo,
        residents_repo,
        UsersRepo(session),
        orgs_repo,
        files_service,
        GroupingService(requests_repo, events),
        make_notifications_service(session),
        events,
        YandexClassifier(make_config().yandex),
    )
    return ChargesService(
        ChargesRepo(session),
        meters_repo,
        houses_repo,
        access,
        readings_service,
        requests_service,
        events,
    )


async def _add_resident(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    flat_id: FlatId | None,
    *,
    role: ResidentRole = ResidentRole.OWNER,
    verified: bool = True,
    can_see_charges: bool | None = None,
) -> Resident:
    is_owner = role is ResidentRole.OWNER
    resident = Resident(
        user_id=user_id,
        house_id=house_id,
        flat_id=flat_id,
        role=role,
        can_see_charges=is_owner if can_see_charges is None else can_see_charges,
        can_vote=is_owner,
        verified_at=datetime.now(UTC) if verified else None,
    )
    session.add(resident)
    await session.flush()
    return resident


async def _add_tariff(
    session: AsyncSession,
    house_id: HouseId,
    service: ServiceType,
    value: int,
    valid_from: date,
) -> Tariff:
    tariff = Tariff(
        house_id=house_id,
        service=service,
        value=value,
        unit="m3",
        valid_from=valid_from,
    )
    session.add(tariff)
    await session.flush()
    return tariff


async def _add_charge(
    session: AsyncSession,
    flat_id: FlatId,
    period: date,
    lines: list[dict[str, object]],
    total: int,
    *,
    paid_at: datetime | None = None,
) -> Charge:
    charge = Charge(
        flat_id=flat_id,
        period=period,
        lines=lines,
        total=total,
        is_closed=True,
        paid_at=paid_at,
    )
    session.add(charge)
    await session.flush()
    return charge


def _photo() -> str:
    return f"{uuid4().hex}.jpg"


async def _events(session: AsyncSession, event_type: EventType) -> list[Event]:
    stmt = select(Event).where(events_table.c.type == event_type)
    return list((await session.execute(stmt)).scalars().all())


def _line(
    service: ServiceType,
    amount: int,
    *,
    volume: int | None = None,
    tariff: int | None = None,
    unit: str | None = None,
) -> dict[str, object]:
    return {
        "service": service.value,
        "amount": amount,
        "volume": volume,
        "tariff": tariff,
        "unit": unit,
        "note": None,
    }


# ---------------------------------------------------------------------------
# ChargesRepo
# ---------------------------------------------------------------------------


async def test_tariff_at_picks_the_row_with_the_greatest_valid_from_le_period(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    repo = ChargesRepo(session)
    await _add_tariff(
        session, own.house_id, ServiceType.COLD_WATER, 100_000, date(2025, 1, 1)
    )
    middle = await _add_tariff(
        session, own.house_id, ServiceType.COLD_WATER, 150_000, date(2025, 6, 1)
    )
    await _add_tariff(
        session, own.house_id, ServiceType.COLD_WATER, 200_000, date(2026, 1, 1)
    )

    tariff = await repo.tariff_at(
        own.house_id, ServiceType.COLD_WATER, date(2025, 9, 1)
    )

    assert tariff is not None
    assert tariff.id == middle.id
    assert tariff.value == 150_000


async def test_list_tariffs_orders_newest_valid_from_first(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    repo = ChargesRepo(session)
    await _add_tariff(
        session, own.house_id, ServiceType.COLD_WATER, 100_000, date(2025, 1, 1)
    )
    await _add_tariff(
        session, own.house_id, ServiceType.HOT_WATER, 200_000, date(2026, 1, 1)
    )

    tariffs = await repo.list_tariffs(own.house_id)

    assert [t.valid_from for t in tariffs] == sorted(
        (t.valid_from for t in tariffs), reverse=True
    )


# ---------------------------------------------------------------------------
# Доступ
# ---------------------------------------------------------------------------


async def test_card_refuses_an_unverified_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=False)
    charge = await _add_charge(session, own.flat_id, date(2026, 3, 1), [], 0)
    service = _make_service(session)

    with pytest.raises(NotEnoughRights):
        await service.card(charge.id, own.user_id)


async def test_card_refuses_a_tenant_without_can_see_charges(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(
        session,
        own.user_id,
        own.house_id,
        own.flat_id,
        role=ResidentRole.TENANT,
        verified=True,
        can_see_charges=False,
    )
    charge = await _add_charge(session, own.flat_id, date(2026, 3, 1), [], 0)
    service = _make_service(session)

    with pytest.raises(NotEnoughRights):
        await service.card(charge.id, own.user_id)


async def test_card_refuses_a_foreign_charge_id(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    other = await make_org_house_flat_user()
    other_charge = await _add_charge(session, other.flat_id, date(2026, 3, 1), [], 0)
    service = _make_service(session)

    with pytest.raises(EntityNotFound):
        await service.card(other_charge.id, own.user_id)


async def test_breakdown_refuses_a_foreign_charge_id(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    other = await make_org_house_flat_user()
    other_charge = await _add_charge(session, other.flat_id, date(2026, 3, 1), [], 0)
    service = _make_service(session)

    with pytest.raises(EntityNotFound):
        await service.breakdown(other_charge.id, own.user_id)


# ---------------------------------------------------------------------------
# Карточка и разбор
# ---------------------------------------------------------------------------


async def test_card_lists_the_charge_lines_with_address_and_flat_number(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    charge = await _add_charge(
        session,
        own.flat_id,
        date(2026, 3, 1),
        [_line(ServiceType.COLD_WATER, 1_000, volume=1_000, tariff=100_000, unit="m3")],
        1_000,
    )
    service = _make_service(session)

    card = await service.card(charge.id, own.user_id)

    assert card.flat.id == own.flat_id
    assert card.house.id == own.house_id
    assert len(card.lines) == 1
    assert card.lines[0].service is ServiceType.COLD_WATER


async def test_breakdown_diffs_against_the_charge_one_month_before(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    await _add_charge(
        session,
        own.flat_id,
        date(2026, 2, 1),
        [_line(ServiceType.COLD_WATER, 900, volume=900, tariff=100_000, unit="m3")],
        900,
    )
    charge = await _add_charge(
        session,
        own.flat_id,
        date(2026, 3, 1),
        [_line(ServiceType.COLD_WATER, 1_000, volume=1_000, tariff=100_000, unit="m3")],
        1_000,
    )
    service = _make_service(session)

    data = await service.breakdown(charge.id, own.user_id)

    assert data.previous_charge is not None
    assert data.previous_charge.period == date(2026, 2, 1)
    assert data.delta == 100
    assert data.lines[0].delta.delta == 100
    events = await _events(session, EventType.CHARGE_BREAKDOWN_OPENED)
    assert len(events) == 1
    assert events[0].payload["charge_id"] == charge.id


async def test_breakdown_has_no_previous_charge_for_the_first_period(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    charge = await _add_charge(
        session,
        own.flat_id,
        date(2026, 3, 1),
        [_line(ServiceType.MAINTENANCE, 500)],
        500,
    )
    service = _make_service(session)

    data = await service.breakdown(charge.id, own.user_id)

    assert data.previous_charge is None
    assert data.delta == 500
    assert data.lines[0].delta.kind == "appeared"


async def test_breakdown_includes_the_resident_own_consumption_sparkline(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meters_repo = MetersRepo(session)
    meter = await meters_repo.add(own.flat_id, MeterType.COLD_WATER, 1, "SN-1", None)
    assert meter is not None
    # база предыдущего периода - без нее первая подача не порождает расход
    await meters_repo.add_reading(
        meter.id,
        date(2026, 2, 1),
        {TariffZone.SINGLE: 0},
        [_photo()],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC),
        submitted_by=own.user_id,
    )
    await meters_repo.add_reading(
        meter.id,
        date(2026, 3, 1),
        {TariffZone.SINGLE: 1_000},
        [_photo()],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC),
        submitted_by=own.user_id,
    )
    charge = await _add_charge(
        session,
        own.flat_id,
        date(2026, 3, 1),
        [_line(ServiceType.COLD_WATER, 1_000, volume=1_000, tariff=100_000, unit="m3")],
        1_000,
    )
    service = _make_service(session)

    data = await service.breakdown(charge.id, own.user_id)

    assert len(data.consumption) == 1
    assert data.consumption[0].service is ServiceType.COLD_WATER
    assert data.consumption[0].points[-1].period == date(2026, 3, 1)
    assert data.consumption[0].points[-1].consumption == 1_000


# ---------------------------------------------------------------------------
# Оспаривание начисления
# ---------------------------------------------------------------------------


async def test_dispute_creates_a_charge_dispute_request_with_period_photos(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meters_repo = MetersRepo(session)
    meter = await meters_repo.add(own.flat_id, MeterType.COLD_WATER, 1, "SN-1", None)
    assert meter is not None
    period = date(2026, 3, 1)
    photo = _photo()
    await meters_repo.add_reading(
        meter.id,
        period,
        {TariffZone.SINGLE: 1_000},
        [photo],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC),
        submitted_by=own.user_id,
    )
    charge = await _add_charge(
        session,
        own.flat_id,
        period,
        [_line(ServiceType.COLD_WATER, 1_000, volume=1_000, tariff=100_000, unit="m3")],
        1_000,
    )
    service = _make_service(session)

    request_id = await service.dispute(
        charge.id,
        own.user_id,
        "Почему так много?",
        None,
    )

    requests_repo = RequestsRepo(session)
    request = await requests_repo.get(request_id)
    assert request is not None
    assert request.category is RequestCategory.CHARGE_DISPUTE
    assert "Почему так много?" in request.description
    assert request.flat_id == own.flat_id

    photos = await requests_repo.list_photos(request_id)
    assert [p.path for p in photos] == [photo]

    events = await _events(session, EventType.CHARGE_DISPUTED)
    assert len(events) == 1
    assert events[0].payload["charge_id"] == charge.id
    assert events[0].payload["request_id"] == request_id


async def test_dispute_refuses_a_tenant_without_can_see_charges(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(
        session,
        own.user_id,
        own.house_id,
        own.flat_id,
        role=ResidentRole.TENANT,
        can_see_charges=False,
    )
    charge = await _add_charge(session, own.flat_id, date(2026, 3, 1), [], 0)
    service = _make_service(session)

    with pytest.raises(NotEnoughRights):
        await service.dispute(charge.id, own.user_id, "спор", None)


# ---------------------------------------------------------------------------
# Демо-оплата
# ---------------------------------------------------------------------------


async def test_pay_demo_sets_paid_at_and_refuses_a_second_payment(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    charge = await _add_charge(session, own.flat_id, date(2026, 3, 1), [], 1_000)
    service = _make_service(session)

    result = await service.pay_demo(charge.id, own.user_id)
    assert result.charge_id == charge.id
    assert result.paid_at is not None

    with pytest.raises(InvalidState):
        await service.pay_demo(charge.id, own.user_id)


async def test_pay_demo_refuses_a_foreign_charge_id(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    other = await make_org_house_flat_user()
    other_charge = await _add_charge(session, other.flat_id, date(2026, 3, 1), [], 0)
    service = _make_service(session)

    with pytest.raises(EntityNotFound):
        await service.pay_demo(other_charge.id, own.user_id)


# ---------------------------------------------------------------------------
# Список начислений квартиры
# ---------------------------------------------------------------------------


async def test_list_for_flat_orders_by_period_descending_and_reports_total(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_charge(session, own.flat_id, date(2026, 1, 1), [], 100)
    await _add_charge(session, own.flat_id, date(2026, 3, 1), [], 300)
    await _add_charge(session, own.flat_id, date(2026, 2, 1), [], 200)
    service = _make_service(session)

    charges, total = await service.list_for_flat(own.flat_id, 2, 0)

    assert total == 3
    assert [c.period for c in charges] == [date(2026, 3, 1), date(2026, 2, 1)]
