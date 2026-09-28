from datetime import datetime, timedelta

from zheka.base import ZhekaType
from zheka.core.enums import HouseState, MapPeriod, RequestCategory
from zheka.core.ids import HouseId, OrgId
from zheka.core.models import House
from zheka.core.services.readings import window_period
from zheka.infra.database.repos.admin_map import (
    ActivePoll,
    AdminMapRepo,
    RequestCounts,
    UrgentNotice,
)
from zheka.infra.database.repos.analytics import AnalyticsRepo, SeasonCount
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

URGENT_ACTIVE = timedelta(days=3)

_NO_REQUESTS = RequestCounts()


class AdminMapFilters(ZhekaType):
    states: frozenset[HouseState] = frozenset()
    category: RequestCategory | None = None
    period: MapPeriod = MapPeriod.MONTH
    urgent: bool = False
    poll: bool = False
    reception_today: bool = False
    meters_below: int | None = None
    pending: bool = False


class AdminMapRow(ZhekaType):
    house: House
    counts: RequestCounts
    urgent: UrgentNotice | None
    poll: ActivePoll | None
    poll_turnout: int | None
    appointments_today: int
    meters: SeasonCount | None
    flats_count: int
    residents_count: int | None
    verified_residents: int | None
    pending_verifications: int | None
    chat_bound: bool | None

    def matches(self, filters: AdminMapFilters, can_manage: bool) -> bool:
        checks = (
            not filters.states or self.counts.state in filters.states,
            not filters.urgent or self.urgent is not None,
            not filters.poll or self.poll is not None,
            not filters.reception_today or self.appointments_today > 0,
            filters.meters_below is None
            or (
                self.meters is not None
                and self.meters.percent < filters.meters_below * 100
            ),
            not (filters.pending and can_manage)
            or (self.pending_verifications or 0) > 0,
        )
        return all(checks)


class AdminMapData(ZhekaType):
    items: list[AdminMapRow]
    without_coords: int


class AdminMapService:
    __slots__ = ("_analytics", "_houses", "_map", "_orgs", "_residents")

    def __init__(
        self,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        admin_map_repo: AdminMapRepo,
        analytics_repo: AnalyticsRepo,
        orgs_repo: OrgsRepo,
    ) -> None:
        self._houses = houses_repo
        self._residents = residents_repo
        self._map = admin_map_repo
        self._analytics = analytics_repo
        self._orgs = orgs_repo

    async def houses(
        self,
        org_id: OrgId,
        can_manage: bool,
        filters: AdminMapFilters,
        now: datetime,
    ) -> AdminMapData:
        houses = await self._houses.list_for_org(org_id)
        house_ids = [house.id for house in houses]
        counts = await self._map.request_counts(
            org_id,
            filters.category,
            now - filters.period.span,
            now,
        )
        urgent = await self._map.urgent_notices(org_id, now - URGENT_ACTIVE)
        polls = await self._map.active_polls(org_id, now)
        org = await self._orgs.get_existing(org_id)
        today = org.local(now).date()
        appointments = await self._map.appointments_between(
            org_id,
            org.day_start(today),
            org.day_start(today + timedelta(days=1)),
        )
        period = window_period(today, await self._orgs.get_settings(org_id))
        meters = await self._analytics.season(org_id, period)
        flats = await self._houses.count_flats_by_house(house_ids)
        residents: dict[HouseId, int] = {}
        verified: dict[HouseId, int] = {}
        pending: dict[HouseId, int] = {}
        chats: dict[HouseId, str | None] = {}
        if can_manage:
            residents = await self._residents.count_by_house(house_ids)
            verified = await self._map.verified_by_house(house_ids)
            pending = await self._map.pending_by_house(house_ids)
            chats = await self._houses.bound_chat_titles(house_ids)
        rows = []
        for house in houses:
            poll = polls.get(house.id)
            flats_count = flats.get(house.id, 0)
            rows.append(
                AdminMapRow(
                    house=house,
                    counts=counts.get(house.id, _NO_REQUESTS),
                    urgent=urgent.get(house.id),
                    poll=poll,
                    poll_turnout=None
                    if poll is None or not flats_count
                    else poll.voted_flats * 10000 // flats_count,
                    appointments_today=appointments.get(house.id, 0),
                    meters=meters.get(house.id),
                    flats_count=flats_count,
                    residents_count=residents.get(house.id, 0) if can_manage else None,
                    verified_residents=verified.get(house.id, 0)
                    if can_manage
                    else None,
                    pending_verifications=pending.get(house.id, 0)
                    if can_manage
                    else None,
                    chat_bound=house.id in chats if can_manage else None,
                ),
            )
        matched = [row for row in rows if row.matches(filters, can_manage)]
        located = [
            row
            for row in matched
            if row.house.lat is not None and row.house.lon is not None
        ]
        return AdminMapData(items=located, without_coords=len(matched) - len(located))
