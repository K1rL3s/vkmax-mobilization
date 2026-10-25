from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import Fixture, add_resident, add_user, requests_service

from zheka.core.enums import (
    RequestCategory,
    RequestCompletionReason,
    RequestPlace,
    RequestStatus,
    ResidentRole,
    ResidentStatus,
    ServiceType,
)
from zheka.core.ids import HouseId
from zheka.core.models import House
from zheka.core.recalculation import (
    MONTHLY_NORM_HOURS,
    Recalculation,
    recalculation,
)
from zheka.core.services.requests import RequestDraft
from zheka.infra.database.models import Charge
from zheka.infra.database.repos.requests import RequestsRepo

FILED = datetime(2026, 9, 10, 7, tzinfo=UTC)


@pytest.mark.parametrize(
    ("service", "norm"),
    [
        (ServiceType.COLD_WATER, 8),
        (ServiceType.HOT_WATER, 8),
        (ServiceType.ELECTRICITY, 24),
        (ServiceType.GAS, 4),
        (ServiceType.HEATING, 24),
    ],
)
def test_the_reduction_starts_with_the_first_full_hour_over_the_monthly_norm(
    service: ServiceType,
    norm: int,
) -> None:
    assert MONTHLY_NORM_HOURS[service] == norm
    assert recalculation(service, norm, 100_000) == Recalculation(
        hours_over=0,
        amount=0,
    )
    assert recalculation(service, norm + 1, 100_000) == Recalculation(
        hours_over=1,
        amount=150,
    )


def test_two_days_without_water_take_six_percent_of_the_water_charge() -> None:
    assert recalculation(ServiceType.COLD_WATER, 48, 100_000) == Recalculation(
        hours_over=40,
        amount=6_000,
    )


def test_two_days_without_light_take_three_point_six_percent() -> None:
    assert recalculation(ServiceType.ELECTRICITY, 48, 150_000).amount == 5_400


def test_the_reduction_rounds_down_to_a_kopeck_and_stops_at_the_whole_charge() -> None:
    assert recalculation(ServiceType.HEATING, 25, 999).amount == 1
    assert recalculation(ServiceType.HEATING, 690, 250_000).amount == 249_750
    assert recalculation(ServiceType.HEATING, 2_000, 250_000).amount == 250_000


def _house() -> House:
    return House(
        id=HouseId(1),
        region="Москва",
        city="Москва",
        street="Тестовая",
        building="1",
        chat_binding_code="abcd1234",
        timezone="Europe/Moscow",
    )


def test_hours_split_at_the_house_local_month_and_drop_a_part_hour() -> None:
    start = datetime(2026, 9, 30, 12, 30, tzinfo=UTC)

    hours = _house().hours_by_month(start, start + timedelta(hours=30))

    assert hours == {date(2026, 9, 1): 8, date(2026, 10, 1): 21}


async def _estimate(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    *,
    verified: bool = True,
    service: ServiceType = ServiceType.COLD_WATER,
    reason: RequestCompletionReason | None = None,
    role: ResidentRole = ResidentRole.OWNER,
    blocked: bool = False,
    hours: int = 48,
    category: RequestCategory = RequestCategory.WATER_SUPPLY,
    filed: datetime = FILED,
) -> Recalculation | None:
    own = await make_org_house_flat_user()
    resident = await add_resident(
        session,
        own.user_id,
        own.house_id,
        own.flat_id,
        role=role,
        verified=verified,
    )
    if role is ResidentRole.TENANT:
        owner = await add_user(session)
        await add_resident(session, owner, own.house_id, own.flat_id)
    line = {"service": service.value, "amount": 100_000}
    session.add(
        Charge(flat_id=own.flat_id, period=date(2026, 1, 1), lines=[line], total=1),
    )
    service_ = requests_service(session)
    card = await service_.create(
        own.user_id,
        own.house_id,
        RequestDraft(
            category=category,
            description="Нет воды",
            flat_id=own.flat_id,
            place=RequestPlace.FLAT,
        ),
    )
    request = card.request
    request.created_at = filed
    request.status = RequestStatus.ON_REVIEW if reason is None else RequestStatus.DONE
    request.completion_reason = reason
    canceled = reason is RequestCompletionReason.RESIDENT_CANCELED
    await RequestsRepo(session).add_log(
        request.id,
        RequestStatus.IN_PROGRESS,
        RequestStatus.DONE if canceled else RequestStatus.ON_REVIEW,
        None,
        "resident" if canceled else "staff",
        filed + timedelta(hours=hours),
    )
    if blocked:
        resident.status = ResidentStatus.BLOCKED
    await session.flush()
    return (await service_.get_card(own.user_id, request.id)).recalculation


async def test_the_card_estimates_two_days_without_water(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    recalc = await _estimate(session, make_org_house_flat_user)

    assert recalc == Recalculation(hours_over=40, amount=6_000)


async def test_no_estimate_without_a_charge_for_the_service(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    recalc = await _estimate(
        session,
        make_org_house_flat_user,
        service=ServiceType.MAINTENANCE,
    )

    assert recalc is None


async def test_no_estimate_for_an_unverified_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    recalc = await _estimate(session, make_org_house_flat_user, verified=False)

    assert recalc is None


async def test_no_estimate_once_the_resident_rejected_the_work(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    recalc = await _estimate(
        session,
        make_org_house_flat_user,
        reason=RequestCompletionReason.RESIDENT_REJECTED,
    )

    assert recalc is None


async def test_no_estimate_for_a_canceled_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    recalc = await _estimate(
        session,
        make_org_house_flat_user,
        reason=RequestCompletionReason.RESIDENT_CANCELED,
    )

    assert recalc is None


async def test_no_estimate_for_a_blocked_author(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    recalc = await _estimate(session, make_org_house_flat_user, blocked=True)

    assert recalc is None


async def test_no_estimate_for_a_tenant_though_the_owner_sees_charges(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    recalc = await _estimate(
        session,
        make_org_house_flat_user,
        role=ResidentRole.TENANT,
    )

    assert recalc is None


async def test_no_estimate_within_the_monthly_norm(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    recalc = await _estimate(session, make_org_house_flat_user, hours=8)

    assert recalc is None


async def test_heating_counts_only_the_hours_of_the_heating_season(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    recalc = await _estimate(
        session,
        make_org_house_flat_user,
        service=ServiceType.HEATING,
        category=RequestCategory.HEATING,
        filed=datetime(2026, 9, 28, 21, tzinfo=UTC),
        hours=96,
    )

    assert recalc == Recalculation(hours_over=24, amount=3_600)


async def test_no_heating_estimate_in_summer(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    recalc = await _estimate(
        session,
        make_org_house_flat_user,
        service=ServiceType.HEATING,
        category=RequestCategory.HEATING,
        filed=datetime(2026, 6, 10, 7, tzinfo=UTC),
    )

    assert recalc is None
