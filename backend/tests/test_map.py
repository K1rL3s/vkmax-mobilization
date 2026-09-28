import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import add_user

from zheka.core.enums import (
    MapHouseKind,
    RequestCategory,
    RequestChannel,
    RequestStatus,
)
from zheka.core.ids import HouseId, OrgId
from zheka.core.models import House, Organization, Request
from zheka.core.services.map import Box, MapFilters, MapService
from zheka.infra.database.repos.analytics import AnalyticsRepo
from zheka.infra.database.repos.map import MapRepo
from zheka.infra.database.tables.residents import demand_signals_table

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


def _service(session: AsyncSession) -> MapService:
    return MapService(MapRepo(session), AnalyticsRepo(session))


def _box(lat: float, lon: float) -> Box:
    return Box(west=lon - 0.01, south=lat - 0.01, east=lon + 0.01, north=lat + 0.01)


def _spot() -> tuple[float, float]:
    return -40 - secrets.randbelow(10_000) / 1000, -150 - secrets.randbelow(
        10_000,
    ) / 1000


async def _org(session: AsyncSession, *, registered: bool = True) -> OrgId:
    org = Organization(
        name=f"УК {secrets.token_hex(4)}",
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Картоград, Тестовая, 1",
        registered_at=NOW if registered else None,
        timezone="Europe/Moscow",
    )
    session.add(org)
    await session.flush()
    return org.id


async def _house(
    session: AsyncSession,
    org_id: OrgId | None,
    lat: float,
    lon: float,
    *,
    added: bool = False,
) -> HouseId:
    house = House(
        org_id=org_id,
        region="Картовая область",
        city="Картоград",
        street="Тестовая",
        building=secrets.token_hex(2),
        lat=Decimal(str(round(lat, 6))),
        lon=Decimal(str(round(lon, 6))),
        chat_binding_code=secrets.token_hex(4),
        timezone="Europe/Moscow",
        added_by_resident=added,
    )
    session.add(house)
    await session.flush()
    return house.id


async def _closed_requests(
    session: AsyncSession,
    house_id: HouseId,
    count: int,
    *,
    on_time: bool,
    rating: int,
) -> None:
    created_at = NOW - timedelta(days=5)
    deadline_at = created_at + timedelta(days=1)
    reviewed_at = deadline_at + (-timedelta(hours=1) if on_time else timedelta(hours=1))
    session.add_all(
        [
            Request(
                house_id=house_id,
                category=RequestCategory.OTHER,
                description="Заявка",
                status=RequestStatus.DONE,
                channel=RequestChannel.MINIAPP,
                deadline_at=deadline_at,
                created_at=created_at,
                reviewed_at=reviewed_at,
                done_at=reviewed_at,
                rating=rating,
            )
            for _ in range(count)
        ],
    )
    await session.flush()


async def test_only_houses_inside_the_box_are_returned(session: AsyncSession) -> None:
    lat, lon = _spot()
    org_id = await _org(session)
    inside = await _house(session, org_id, lat, lon)
    await _house(session, org_id, lat + 0.05, lon)

    data = await _service(session).houses(_box(lat, lon), MapFilters(), NOW)

    assert [row.house.id for row in data.items] == [inside]
    assert data.total == 1


async def test_a_house_kind_follows_the_org_registration_and_the_resident_flag(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    connected = await _house(session, await _org(session), lat, lon)
    unconnected = await _house(
        session,
        await _org(session, registered=False),
        lat + 0.001,
        lon,
    )
    added = await _house(session, None, lat + 0.002, lon, added=True)

    data = await _service(session).houses(_box(lat, lon), MapFilters(), NOW)

    assert {row.house.id: row.kind for row in data.items} == {
        connected: MapHouseKind.CONNECTED,
        unconnected: MapHouseKind.UNCONNECTED,
        added: MapHouseKind.ADDED,
    }


async def test_kinds_filter_keeps_only_the_asked_kinds(session: AsyncSession) -> None:
    lat, lon = _spot()
    await _house(session, await _org(session), lat, lon)
    added = await _house(session, None, lat + 0.001, lon, added=True)

    data = await _service(session).houses(
        _box(lat, lon),
        MapFilters(kinds=frozenset({MapHouseKind.ADDED})),
        NOW,
    )

    assert [row.house.id for row in data.items] == [added]


async def test_org_stats_come_only_with_ten_closed_requests(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    enough_org = await _org(session)
    few_org = await _org(session)
    enough = await _house(session, enough_org, lat, lon)
    few = await _house(session, few_org, lat + 0.001, lon)
    await _closed_requests(session, enough, 10, on_time=True, rating=4)
    await _closed_requests(session, few, 9, on_time=True, rating=4)

    data = await _service(session).houses(_box(lat, lon), MapFilters(), NOW)

    stats = {row.house.id: row.stats for row in data.items}
    enough_stats = stats[enough]
    assert enough_stats is not None
    assert enough_stats.on_time_share == 10_000
    assert enough_stats.rating == 400
    assert stats[few] is None


async def test_on_time_filter_drops_orgs_below_the_bound_and_orgs_without_stats(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    good = await _house(session, await _org(session), lat, lon)
    late = await _house(session, await _org(session), lat + 0.001, lon)
    await _house(session, await _org(session), lat + 0.002, lon)
    await _closed_requests(session, good, 10, on_time=True, rating=5)
    await _closed_requests(session, late, 10, on_time=False, rating=5)

    data = await _service(session).houses(
        _box(lat, lon),
        MapFilters(on_time_from=5000),
        NOW,
    )

    assert [row.house.id for row in data.items] == [good]


async def test_waiting_keeps_only_houses_with_demand(session: AsyncSession) -> None:
    lat, lon = _spot()
    org_id = await _org(session, registered=False)
    wanted = await _house(session, org_id, lat, lon)
    await _house(session, org_id, lat + 0.001, lon)
    user_id = await add_user(session)
    await session.execute(
        insert(demand_signals_table).values(house_id=wanted, user_id=user_id),
    )

    data = await _service(session).houses(
        _box(lat, lon),
        MapFilters(waiting=True),
        NOW,
    )

    assert [(row.house.id, row.demand_count) for row in data.items] == [(wanted, 1)]


async def test_limit_clips_items_but_total_counts_every_match(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    org_id = await _org(session)
    for step in range(3):
        await _house(session, org_id, lat + step * 0.001, lon)

    data = await _service(session).houses(_box(lat, lon), MapFilters(limit=2), NOW)

    assert len(data.items) == 2
    assert data.total == 3


async def test_orgs_list_ignores_the_org_filter(session: AsyncSession) -> None:
    lat, lon = _spot()
    first = await _org(session)
    second = await _org(session)
    await _house(session, first, lat, lon)
    await _house(session, first, lat + 0.001, lon)
    await _house(session, second, lat + 0.002, lon)

    data = await _service(session).houses(
        _box(lat, lon),
        MapFilters(org_ids=frozenset({second})),
        NOW,
    )

    assert {row.org.id: row.houses for row in data.orgs} == {first: 2, second: 1}
    assert {row.org_id for row in (item.house for item in data.items)} == {second}


async def test_a_connected_house_shows_no_demand_and_is_not_waiting(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    connected = await _house(session, await _org(session), lat, lon)
    await session.execute(
        insert(demand_signals_table).values(
            house_id=connected,
            user_id=await add_user(session),
        ),
    )
    service = _service(session)

    shown = await service.houses(_box(lat, lon), MapFilters(), NOW)
    waiting = await service.houses(_box(lat, lon), MapFilters(waiting=True), NOW)

    assert [row.demand_count for row in shown.items] == [0]
    assert waiting.items == []


async def test_an_unregistered_org_gets_no_public_stats(session: AsyncSession) -> None:
    lat, lon = _spot()
    house_id = await _house(session, await _org(session, registered=False), lat, lon)
    await _closed_requests(session, house_id, 10, on_time=True, rating=5)

    data = await _service(session).houses(_box(lat, lon), MapFilters(), NOW)

    assert [row.stats for row in data.items] == [None]
    assert data.orgs == []
