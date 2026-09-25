from collections.abc import Awaitable, Callable
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    add_meter,
    add_reading,
    add_resident,
    add_tariff,
    events_of,
    make_config,
    requests_service,
)

from zheka.core.enums import (
    EventType,
    RequestCategory,
    ResidentRole,
    ServiceType,
)
from zheka.core.errors import EntityNotFound, InvalidState, NotEnoughRights
from zheka.core.ids import ChargeId, FlatId, UserId
from zheka.core.services.charges import ChargesService
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.meter_access import MeterAccess
from zheka.core.services.readings import ReadingsService
from zheka.infra.database.models import Charge
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo


def _make_service(session: AsyncSession) -> ChargesService:
    meters_repo = MetersRepo(session)
    houses_repo = HousesRepo(session)
    residents_repo = ResidentsRepo(session)
    orgs_repo = OrgsRepo(session)
    events = EventsService(EventsRepo(session))
    access = MeterAccess(meters_repo, houses_repo, residents_repo, orgs_repo)
    readings_service = ReadingsService(
        meters_repo,
        ChargesRepo(session),
        orgs_repo,
        access,
        FilesService(make_config().files, "test-token"),
        events,
    )
    return ChargesService(
        ChargesRepo(session),
        meters_repo,
        access,
        readings_service,
        requests_service(session),
        events,
    )


async def _add_charge(
    session: AsyncSession,
    flat_id: FlatId,
    period: date,
    lines: list[dict[str, object]],
    total: int,
) -> Charge:
    charge = Charge(
        flat_id=flat_id,
        period=period,
        lines=lines,
        total=total,
        is_closed=True,
    )
    session.add(charge)
    await session.flush()
    return charge


async def _charge(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    period: date = date(2026, 3, 1),
    amount: int = 1_000,
) -> Charge:
    line = {
        "service": ServiceType.COLD_WATER.value,
        "amount": amount,
        "volume": amount,
        "tariff": 100_000,
        "unit": "m3",
    }
    return await _add_charge(session, own.flat_id, period, [line], amount)


async def test_tariffs_come_newest_first_and_tariff_at_takes_the_one_in_force(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    service = ServiceType.COLD_WATER
    starts = [date(2025, 1, 1), date(2026, 1, 1), date(2025, 6, 1)]
    added = [
        await add_tariff(session, own.house_id, 100_000, service, start)
        for start in starts
    ]

    tariffs = await _make_service(session).tariffs(own.house_id)
    in_force = await ChargesRepo(session).tariff_at(
        own.house_id,
        service,
        date(2025, 9, 1),
    )

    assert [t.valid_from for t in tariffs] == sorted(starts, reverse=True)
    assert in_force is not None
    assert in_force.id == added[2].id


_CALLS: dict[str, Callable[[ChargesService, ChargeId, UserId], Awaitable[object]]] = {
    "card": lambda service, charge_id, user_id: service.card(charge_id, user_id),
    "breakdown": lambda service, charge_id, user_id: service.breakdown(
        charge_id,
        user_id,
    ),
    "dispute": lambda service, charge_id, user_id: service.dispute(
        charge_id,
        user_id,
        "спор",
        None,
    ),
    "pay": lambda service, charge_id, user_id: service.pay_demo(charge_id, user_id),
}


@pytest.mark.parametrize(
    ("call", "role", "verified"),
    [
        ("card", ResidentRole.OWNER, False),
        ("card", ResidentRole.TENANT, True),
        ("dispute", ResidentRole.TENANT, True),
    ],
)
async def test_charges_need_a_verified_resident_with_can_see_charges(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    call: str,
    role: ResidentRole,
    verified: bool,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(
        session,
        own.user_id,
        own.house_id,
        own.flat_id,
        role=role,
        verified=verified,
    )
    charge = await _charge(session, own)

    with pytest.raises(NotEnoughRights):
        await _CALLS[call](_make_service(session), charge.id, own.user_id)


@pytest.mark.parametrize("call", ["card", "breakdown", "pay"])
async def test_a_foreign_charge_id_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    call: str,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    other_charge = await _charge(session, await make_org_house_flat_user())

    with pytest.raises(EntityNotFound):
        await _CALLS[call](_make_service(session), other_charge.id, own.user_id)


async def test_card_lists_the_charge_lines_with_address_and_flat_number(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    charge = await _charge(session, own)

    card = await _make_service(session).card(charge.id, own.user_id)

    assert card.flat.id == own.flat_id
    assert card.house.id == own.house_id
    assert [line.service for line in card.lines] == [ServiceType.COLD_WATER]


async def test_breakdown_diffs_against_the_charge_one_month_before(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    await _charge(session, own, date(2026, 2, 1), 900)
    charge = await _charge(session, own)

    data = await _make_service(session).breakdown(charge.id, own.user_id)

    assert data.previous_charge is not None
    assert data.previous_charge.period == date(2026, 2, 1)
    assert data.delta == 100
    assert data.lines[0].delta.delta == 100
    events = await events_of(session, EventType.CHARGE_BREAKDOWN_OPENED)
    assert len(events) == 1
    assert events[0].payload["charge_id"] == charge.id


async def test_breakdown_has_no_previous_charge_for_the_first_period(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    charge = await _add_charge(
        session,
        own.flat_id,
        date(2026, 3, 1),
        [{"service": ServiceType.MAINTENANCE.value, "amount": 500}],
        500,
    )

    data = await _make_service(session).breakdown(charge.id, own.user_id)

    assert data.previous_charge is None
    assert data.delta == 500
    assert data.lines[0].delta.kind == "appeared"


async def test_breakdown_includes_the_resident_own_consumption_sparkline(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await add_meter(session, own.flat_id)
    await add_reading(session, meter_id, date(2026, 2, 1), 0, own.user_id)
    await add_reading(session, meter_id, date(2026, 3, 1), 1_000, own.user_id)
    charge = await _charge(session, own)

    data = await _make_service(session).breakdown(charge.id, own.user_id)

    assert len(data.consumption) == 1
    assert data.consumption[0].service is ServiceType.COLD_WATER
    assert data.consumption[0].points[-1].period == date(2026, 3, 1)
    assert data.consumption[0].points[-1].consumption == 1_000


async def test_dispute_creates_a_charge_dispute_request_with_period_photos(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await add_meter(session, own.flat_id)
    await add_reading(session, meter_id, date(2026, 3, 1), 1_000, own.user_id)
    charge = await _charge(session, own)

    request_id = await _make_service(session).dispute(
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
    [reading] = await MetersRepo(session).list_readings(meter_id, 1)
    assert [p.path for p in photos] == reading.photo_paths
    events = await events_of(session, EventType.CHARGE_DISPUTED)
    assert len(events) == 1
    assert events[0].payload["charge_id"] == charge.id
    assert events[0].payload["request_id"] == request_id


async def test_pay_demo_sets_paid_at_and_refuses_a_second_payment(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    charge = await _charge(session, own)
    service = _make_service(session)

    result = await service.pay_demo(charge.id, own.user_id)
    assert result.charge_id == charge.id
    assert charge.paid_at == result.paid_at

    with pytest.raises(InvalidState):
        await service.pay_demo(charge.id, own.user_id)


async def test_list_for_flat_orders_by_period_descending_and_reports_total(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    for month in (1, 3, 2):
        await _add_charge(session, own.flat_id, date(2026, month, 1), [], 100)

    charges, total = await _make_service(session).list_for_flat(own.flat_id, 2, 0)

    assert total == 3
    assert [c.period for c in charges] == [date(2026, 3, 1), date(2026, 2, 1)]
