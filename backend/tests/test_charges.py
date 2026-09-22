from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser, make_config, make_notifications_service
from tests.test_requests import _StubClassifier, _events, _photo

from zheka.core.enums import (
    EventType,
    MeterType,
    RequestCategory,
    ResidentRole,
    ServiceType,
    TariffZone,
)
from zheka.core.errors import EntityNotFound, InvalidState, NotEnoughRights
from zheka.core.ids import ChargeId, FlatId, HouseId, MeterId, UserId
from zheka.core.services.charges import ChargesService
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.meter_access import MeterAccess
from zheka.core.services.readings import ReadingsService
from zheka.core.services.request_groups import GroupingService
from zheka.core.services.requests import RequestsService
from zheka.infra.database.models import Charge, Resident, Tariff
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

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
        _StubClassifier(None),
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
    own: OrgHouseFlatUser,
    *,
    role: ResidentRole = ResidentRole.OWNER,
    verified: bool = True,
) -> None:
    is_owner = role is ResidentRole.OWNER
    session.add(
        Resident(
            user_id=own.user_id,
            house_id=own.house_id,
            flat_id=own.flat_id,
            role=role,
            can_see_charges=is_owner,
            can_vote=is_owner,
            verified_at=datetime.now(UTC) if verified else None,
        ),
    )
    await session.flush()


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


async def _add_reading(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    meter_id: MeterId,
    period: date,
    value: int,
    photo: str,
) -> None:
    await MetersRepo(session).add_reading(
        meter_id,
        period,
        {TariffZone.SINGLE: value},
        [photo],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC),
        submitted_by=own.user_id,
    )


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


async def test_tariff_at_picks_the_row_with_the_greatest_valid_from_le_period(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_tariff(
        session,
        own.house_id,
        ServiceType.COLD_WATER,
        100_000,
        date(2025, 1, 1),
    )
    middle = await _add_tariff(
        session,
        own.house_id,
        ServiceType.COLD_WATER,
        150_000,
        date(2025, 6, 1),
    )
    await _add_tariff(
        session,
        own.house_id,
        ServiceType.COLD_WATER,
        200_000,
        date(2026, 1, 1),
    )

    tariff = await ChargesRepo(session).tariff_at(
        own.house_id,
        ServiceType.COLD_WATER,
        date(2025, 9, 1),
    )

    assert tariff is not None
    assert tariff.id == middle.id


async def test_tariffs_list_newest_valid_from_first(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_tariff(
        session,
        own.house_id,
        ServiceType.COLD_WATER,
        100_000,
        date(2025, 1, 1),
    )
    await _add_tariff(
        session,
        own.house_id,
        ServiceType.HOT_WATER,
        200_000,
        date(2026, 1, 1),
    )

    tariffs = await _make_service(session).tariffs(own.house_id)

    assert [t.valid_from for t in tariffs] == [date(2026, 1, 1), date(2025, 1, 1)]


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
    await _add_resident(session, own, role=role, verified=verified)
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
    await _add_resident(session, own)
    other_charge = await _charge(session, await make_org_house_flat_user())

    with pytest.raises(EntityNotFound):
        await _CALLS[call](_make_service(session), other_charge.id, own.user_id)


async def test_card_lists_the_charge_lines_with_address_and_flat_number(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own)
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
    await _add_resident(session, own)
    await _charge(session, own, date(2026, 2, 1), 900)
    charge = await _charge(session, own)

    data = await _make_service(session).breakdown(charge.id, own.user_id)

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
    await _add_resident(session, own)
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
    await _add_resident(session, own)
    meter = await MetersRepo(session).add(
        own.flat_id,
        MeterType.COLD_WATER,
        1,
        "SN-1",
        None,
    )
    assert meter is not None
    await _add_reading(session, own, meter.id, date(2026, 2, 1), 0, _photo())
    await _add_reading(session, own, meter.id, date(2026, 3, 1), 1_000, _photo())
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
    await _add_resident(session, own)
    meter = await MetersRepo(session).add(
        own.flat_id,
        MeterType.COLD_WATER,
        1,
        "SN-1",
        None,
    )
    assert meter is not None
    photo = _photo()
    await _add_reading(session, own, meter.id, date(2026, 3, 1), 1_000, photo)
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
    assert [p.path for p in photos] == [photo]
    events = await _events(session, EventType.CHARGE_DISPUTED)
    assert len(events) == 1
    assert events[0].payload["charge_id"] == charge.id
    assert events[0].payload["request_id"] == request_id


async def test_pay_demo_sets_paid_at_and_refuses_a_second_payment(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own)
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
