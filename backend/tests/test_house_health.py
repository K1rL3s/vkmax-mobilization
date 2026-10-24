from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser
from tests.test_houses import _add_house, _make_service

from zheka.api.schemas.houses import HouseCard
from zheka.core.enums import (
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestGroupStatus,
    RequestPlace,
    RequestStatus,
)
from zheka.core.ids import HouseId, RequestGroupId, RequestId
from zheka.infra.database.models import Request, RequestGroup

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


async def _request(
    session: AsyncSession,
    house_id: HouseId,
    category: RequestCategory,
    *,
    place: RequestPlace = RequestPlace.HOUSE,
    days_ago: int = 1,
    completion: RequestCompletionReason | None = None,
    group_id: RequestGroupId | None = None,
    parent_id: RequestId | None = None,
) -> RequestId:
    created_at = datetime.now(UTC) - timedelta(days=days_ago)
    request = Request(
        house_id=house_id,
        category=category,
        description="Проблема",
        status=RequestStatus.NEW if completion is None else RequestStatus.DONE,
        completion_reason=completion,
        channel=RequestChannel.MINIAPP,
        created_at=created_at,
        deadline_at=created_at + timedelta(days=3),
        done_at=None if completion is None else created_at + timedelta(hours=5),
        place=place,
        group_id=group_id,
        parent_request_id=parent_id,
    )
    session.add(request)
    await session.flush()
    return request.id


async def _group(
    session: AsyncSession,
    house_id: HouseId,
    category: RequestCategory,
) -> RequestGroupId:
    group = RequestGroup(
        house_id=house_id,
        category=category,
        window_started_at=datetime.now(UTC),
        status=RequestGroupStatus.OPEN,
    )
    session.add(group)
    await session.flush()
    return group.id


async def _health(
    session: AsyncSession,
    fixture: OrgHouseFlatUser,
    house_id: HouseId | None = None,
) -> dict[str, tuple[int, int, int]] | None:
    card = await _make_service(session).house_card(
        house_id or fixture.house_id,
        fixture.user_id,
        datetime.now(UTC),
    )
    health = HouseCard.of(card, []).health
    if health is None:
        return None
    return {row.system: (row.reported, row.resolved, row.open) for row in health}


async def test_a_house_without_shared_requests_is_fine_everywhere(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()

    assert await _health(session, fixture) == {
        "water": (0, 0, 0),
        "heating": (0, 0, 0),
        "electricity": (0, 0, 0),
        "garbage": (0, 0, 0),
        "entrance": (0, 0, 0),
        "yard": (0, 0, 0),
    }


async def test_a_house_of_an_unconnected_org_has_no_health_block(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user(registered=False)
    await _request(session, fixture.house_id, RequestCategory.GARBAGE)

    assert await _health(session, fixture) is None


async def test_personal_requests_do_not_change_the_numbers(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    await _request(
        session,
        fixture.house_id,
        RequestCategory.HEATING,
        completion=RequestCompletionReason.RESIDENT_ACCEPTED,
    )
    await _request(
        session,
        fixture.house_id,
        RequestCategory.HEATING,
        place=RequestPlace.FLAT,
    )
    await _request(
        session,
        fixture.house_id,
        RequestCategory.LEAK,
        place=RequestPlace.FLAT,
    )
    await _request(session, fixture.house_id, RequestCategory.OTHER)

    health = await _health(session, fixture)

    assert health is not None
    assert health["heating"] == (1, 1, 0)
    assert health["water"] == (0, 0, 0)


async def test_a_collective_request_and_its_repeats_are_one_problem(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    leak = await _group(session, fixture.house_id, RequestCategory.LEAK)
    grouped = await _request(
        session,
        fixture.house_id,
        RequestCategory.LEAK,
        days_ago=4,
        completion=RequestCompletionReason.RESIDENT_REJECTED,
        group_id=leak,
    )
    await _request(
        session,
        fixture.house_id,
        RequestCategory.LEAK,
        completion=RequestCompletionReason.RESIDENT_ACCEPTED,
        group_id=leak,
    )
    await _request(session, fixture.house_id, RequestCategory.LEAK, group_id=leak)
    await _request(session, fixture.house_id, RequestCategory.LEAK, parent_id=grouped)
    first = await _request(
        session,
        fixture.house_id,
        RequestCategory.WATER_SUPPLY,
        days_ago=3,
        completion=RequestCompletionReason.RESIDENT_REJECTED,
    )
    second = await _request(
        session,
        fixture.house_id,
        RequestCategory.WATER_SUPPLY,
        days_ago=2,
        completion=RequestCompletionReason.RESIDENT_REJECTED,
        parent_id=first,
    )
    await _request(
        session,
        fixture.house_id,
        RequestCategory.WATER_SUPPLY,
        completion=RequestCompletionReason.AUTO_CLOSED,
        parent_id=second,
    )

    health = await _health(session, fixture)

    assert health is not None
    assert health["water"] == (2, 1, 1)


async def test_an_open_problem_older_than_two_weeks_stays_and_a_closed_one_goes(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    await _request(session, fixture.house_id, RequestCategory.GARBAGE, days_ago=30)
    await _request(
        session,
        fixture.house_id,
        RequestCategory.GARBAGE,
        days_ago=15,
        completion=RequestCompletionReason.RESIDENT_ACCEPTED,
    )
    await _request(
        session,
        fixture.house_id,
        RequestCategory.YARD,
        completion=RequestCompletionReason.RESIDENT_CANCELED,
    )

    health = await _health(session, fixture)

    assert health is not None
    assert health["garbage"] == (1, 0, 1)
    assert health["yard"] == (0, 0, 0)


async def test_the_lift_shows_from_six_floors_or_after_any_lift_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    low = await _add_house(session, fixture.org_id, floors=5)
    tall = await _add_house(session, fixture.org_id, floors=6)

    assert "elevator" not in (await _health(session, fixture, low) or {})
    assert (await _health(session, fixture, tall) or {})["elevator"] == (0, 0, 0)

    await _request(
        session,
        low,
        RequestCategory.ELEVATOR,
        place=RequestPlace.FLAT,
        days_ago=200,
        completion=RequestCompletionReason.RESIDENT_CANCELED,
    )

    assert (await _health(session, fixture, low) or {})["elevator"] == (0, 0, 0)
