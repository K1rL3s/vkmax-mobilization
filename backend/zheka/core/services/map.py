from datetime import datetime

from zheka.base import ZhekaType
from zheka.core.enums import MapHouseKind
from zheka.core.ids import OrgId
from zheka.core.models import House, Organization
from zheka.core.services.houses import (
    PUBLIC_STATS_MIN_CLOSED,
    PUBLIC_STATS_PERIOD,
    is_connected,
)
from zheka.infra.database.repos.analytics import AnalyticsRepo, PublicStats
from zheka.infra.database.repos.map import MapRepo

MAP_LIMIT = 5000


class Box(ZhekaType):
    west: float
    south: float
    east: float
    north: float


class MapFilters(ZhekaType):
    kinds: frozenset[MapHouseKind] = frozenset()
    org_ids: frozenset[OrgId] = frozenset()
    waiting: bool = False
    on_time_from: int | None = None
    on_time_to: int | None = None
    rating_from: int | None = None
    rating_to: int | None = None
    limit: int = MAP_LIMIT

    @property
    def wants_stats(self) -> bool:
        return any(
            bound is not None
            for bound in (
                self.on_time_from,
                self.on_time_to,
                self.rating_from,
                self.rating_to,
            )
        )


class MapHouseRow(ZhekaType):
    house: House
    org: Organization | None
    kind: MapHouseKind
    demand_count: int
    stats: PublicStats | None

    def matches(self, filters: MapFilters) -> bool:
        if filters.kinds and self.kind not in filters.kinds:
            return False
        if filters.org_ids and (self.org is None or self.org.id not in filters.org_ids):
            return False
        if filters.waiting and self.demand_count == 0:
            return False
        if not filters.wants_stats:
            return True
        return self.stats is not None and (
            _within(self.stats.on_time_share, filters.on_time_from, filters.on_time_to)
            and _within(self.stats.rating, filters.rating_from, filters.rating_to)
        )


class MapOrgRow(ZhekaType):
    org: Organization
    houses: int


class MapData(ZhekaType):
    items: list[MapHouseRow]
    total: int
    orgs: list[MapOrgRow]


def _within(value: int | None, low: int | None, high: int | None) -> bool:
    if low is None and high is None:
        return True
    if value is None:
        return False
    return (low is None or value >= low) and (high is None or value <= high)


class MapService:
    __slots__ = ("_analytics", "_map")

    def __init__(self, map_repo: MapRepo, analytics_repo: AnalyticsRepo) -> None:
        self._map = map_repo
        self._analytics = analytics_repo

    async def houses(self, box: Box, filters: MapFilters, now: datetime) -> MapData:
        found = await self._map.houses_in_box(box.west, box.south, box.east, box.north)
        connected_orgs = {
            org.id: org
            for house, org, _demand in found
            if org is not None and is_connected(house, org)
        }
        stats = {
            org_id: value
            for org_id, value in (
                await self._analytics.public_stats_by_org(
                    connected_orgs.keys(),
                    now - PUBLIC_STATS_PERIOD,
                    now,
                )
            ).items()
            if value.closed >= PUBLIC_STATS_MIN_CLOSED
        }
        rows = [
            MapHouseRow(
                house=house,
                org=org,
                kind=_kind(house, org),
                demand_count=0 if is_connected(house, org) else demand,
                stats=None if org is None else stats.get(org.id),
            )
            for house, org, demand in found
        ]
        org_counts: dict[OrgId, int] = {}
        for row in rows:
            if row.kind is MapHouseKind.CONNECTED and row.org is not None:
                org_counts[row.org.id] = org_counts.get(row.org.id, 0) + 1
        matched = [row for row in rows if row.matches(filters)]
        return MapData(
            items=matched[: filters.limit],
            total=len(matched),
            orgs=sorted(
                (
                    MapOrgRow(org=connected_orgs[org_id], houses=count)
                    for org_id, count in org_counts.items()
                ),
                key=lambda row: row.org.name,
            ),
        )


def _kind(house: House, org: Organization | None) -> MapHouseKind:
    if is_connected(house, org):
        return MapHouseKind.CONNECTED
    if house.added_by_resident:
        return MapHouseKind.ADDED
    return MapHouseKind.UNCONNECTED
