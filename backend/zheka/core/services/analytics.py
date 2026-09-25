from calendar import monthrange
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

from zheka.base import ZhekaType
from zheka.core.enums import CATEGORY_RULES, AnalyticsMetric, MetricUnit, RequestChannel
from zheka.core.errors import (
    HOUSE_NOT_FOUND,
    EntityNotFound,
    InvalidRequest,
    InvalidState,
)
from zheka.core.ids import HouseId, OrgId
from zheka.core.models import House, OrgSettings
from zheka.core.services.readings import window_accepts, window_period
from zheka.core.services.reminders import RemindersService
from zheka.infra.database.repos.analytics import (
    AnalyticsRepo,
    ChannelRow,
    ExecutorRow,
    SeasonCount,
)
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo

WINDOW_CLOSED = "Прием показаний закрыт, напомнить можно только в окно подачи"
WRONG_PERIOD = "Напомнить можно только о периоде, который принимается сейчас"

DEFAULT_PERIOD = timedelta(days=30)
WEEKS = 12
UNCONNECTED_LIMIT = 50
_NO_FLATS = SeasonCount(flats_total=0, submitted=0, percent=0)

MIN_ORGS_FOR_CUT = 3


class BenchmarkSpec(ZhekaType):
    metric: AnalyticsMetric
    label: str
    unit: MetricUnit
    lower_is_better: bool


BENCHMARK: tuple[BenchmarkSpec, ...] = (
    BenchmarkSpec(
        metric=AnalyticsMetric.ACCEPT_TIME,
        label="Среднее время до принятия",
        unit=MetricUnit.MINUTES,
        lower_is_better=True,
    ),
    BenchmarkSpec(
        metric=AnalyticsMetric.OVERDUE_SHARE,
        label="Доля просроченных",
        unit=MetricUnit.PERCENT,
        lower_is_better=True,
    ),
    BenchmarkSpec(
        metric=AnalyticsMetric.REPEAT_SHARE,
        label="Доля повторных",
        unit=MetricUnit.PERCENT,
        lower_is_better=True,
    ),
    BenchmarkSpec(
        metric=AnalyticsMetric.AUTO_CLOSED_SHARE,
        label="Доля закрытых по таймауту приемки",
        unit=MetricUnit.PERCENT,
        lower_is_better=True,
    ),
    BenchmarkSpec(
        metric=AnalyticsMetric.DIGITAL_SHARE,
        label="Доля цифровых заявок",
        unit=MetricUnit.PERCENT,
        lower_is_better=False,
    ),
    BenchmarkSpec(
        metric=AnalyticsMetric.RATING,
        label="Средняя оценка",
        unit=MetricUnit.POINTS,
        lower_is_better=False,
    ),
)
CUT_METRIC = BENCHMARK[0]


class Tile(ZhekaType):
    key: str
    label: str
    unit: MetricUnit
    value: int


class Point(ZhekaType):
    label: str
    value: int


class Series(ZhekaType):
    key: str
    title: str
    unit: MetricUnit
    points: list[Point]


class Dashboard(ZhekaType):
    period_from: date
    period_to: date
    tiles: list[Tile]
    charts: list[Series]
    is_empty: bool


class SeasonHouse(ZhekaType):
    house_id: HouseId
    address: str
    flats_total: int
    submitted: int
    not_submitted: int
    percent: int


class Season(ZhekaType):
    period: date
    window_from: date
    window_to: date
    window_open: bool
    submitted: int
    not_submitted: int
    houses: list[SeasonHouse]
    is_empty: bool


class Channels(ZhekaType):
    total: int
    items: list[ChannelRow]
    is_empty: bool


class BenchmarkValue(ZhekaType):
    key: str
    label: str
    unit: MetricUnit
    value: int
    platform_median: int | None
    rank: int | None
    total: int | None


class RegionRow(ZhekaType):
    region: str
    city: str | None
    orgs_count: int
    unit: MetricUnit
    value: int


class UnconnectedHouse(ZhekaType):
    house_id: HouseId
    address: str
    waiting: int


class Benchmark(ZhekaType):
    metrics: list[BenchmarkValue]
    regions: list[RegionRow]
    unconnected_houses: list[UnconnectedHouse]
    is_empty: bool


def _range(
    date_from: date | None,
    date_to: date | None,
    now: datetime,
) -> tuple[date, date]:
    period_to = date_to or now.date()
    period_from = date_from or period_to - DEFAULT_PERIOD
    if period_from > period_to:
        raise InvalidRequest("Начало периода позже его конца")
    return period_from, period_to


def _window(period: date, settings: OrgSettings | None) -> tuple[date, date]:
    last_day = monthrange(period.year, period.month)[1]
    if settings is None or settings.meter_window_always_open:
        return period, period.replace(day=last_day)
    day_from = settings.meter_window_day_from
    day_to = settings.meter_window_day_to
    window_to = period.replace(day=day_to)
    if day_from > day_to:
        window_to = period + timedelta(days=last_day + day_to - 1)
    return period.replace(day=day_from), window_to


class AnalyticsService:
    __slots__ = ("_analytics", "_houses", "_orgs", "_reminders")

    def __init__(
        self,
        analytics_repo: AnalyticsRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        reminders_service: RemindersService,
    ) -> None:
        self._analytics = analytics_repo
        self._houses = houses_repo
        self._orgs = orgs_repo
        self._reminders = reminders_service

    async def dashboard(
        self,
        org_id: OrgId,
        house_id: HouseId | None,
        date_from: date | None,
        date_to: date | None,
        now: datetime,
    ) -> Dashboard:
        if house_id is not None:
            await self._own_houses(org_id, [house_id])
        org = await self._orgs.get_existing(org_id)
        local = org.local(now)
        period_from, period_to = _range(date_from, date_to, local)
        since = org.day_start(period_from)
        until = org.day_start(period_to + timedelta(days=1))
        tiles = await self._analytics.tiles(org_id, house_id, since, until, now)
        categories = await self._analytics.by_category(org_id, house_id, since, until)
        this_week = local.date() - timedelta(days=local.weekday())
        weeks = [this_week - timedelta(weeks=back) for back in range(WEEKS - 1, -1, -1)]
        by_week = await self._analytics.by_week(
            org_id,
            house_id,
            org.day_start(weeks[0]),
            org.timezone,
        )
        dashboard_tiles = [
            Tile(
                key="active",
                label="Активных заявок",
                unit=MetricUnit.COUNT,
                value=tiles.active,
            ),
            Tile(
                key="overdue",
                label="Просрочено по нормативу",
                unit=MetricUnit.COUNT,
                value=tiles.overdue,
            ),
            Tile(
                key=AnalyticsMetric.ACCEPT_TIME.value,
                label="Среднее время до принятия",
                unit=MetricUnit.MINUTES,
                value=tiles.accept_time or 0,
            ),
            Tile(
                key=AnalyticsMetric.REPEAT_SHARE.value,
                label="Доля повторных",
                unit=MetricUnit.PERCENT,
                value=tiles.repeat_share or 0,
            ),
        ]
        charts = [
            Series(
                key="by_category",
                title="Заявки по категориям",
                unit=MetricUnit.COUNT,
                points=[
                    Point(label=CATEGORY_RULES[category].label, value=count)
                    for category, count in categories
                ],
            ),
            Series(
                key="by_week",
                title="Заявки по неделям",
                unit=MetricUnit.COUNT,
                points=[
                    Point(label=week.isoformat(), value=by_week.get(week, 0))
                    for week in weeks
                ],
            ),
        ]
        return Dashboard(
            period_from=period_from,
            period_to=period_to,
            tiles=dashboard_tiles,
            charts=charts,
            is_empty=not any(tile.value for tile in dashboard_tiles)
            and not any(point.value for chart in charts for point in chart.points),
        )

    async def season(self, org_id: OrgId, period: date | None, now: datetime) -> Season:
        settings = await self._orgs.get_settings(org_id)
        if period is None:
            today = (await self._orgs.get_existing(org_id)).local(now).date()
            period = window_period(today, settings)
        period = period.replace(day=1)
        counts = await self._analytics.season(org_id, period)
        org_houses = await self._houses.list_for_org(org_id)
        houses = []
        for house in org_houses:
            count = counts.get(house.id, _NO_FLATS)
            houses.append(
                SeasonHouse(
                    house_id=house.id,
                    address=house.address,
                    flats_total=count.flats_total,
                    submitted=count.submitted,
                    not_submitted=count.flats_total - count.submitted,
                    percent=count.percent,
                ),
            )
        window_from, window_to = _window(period, settings)
        return Season(
            period=period,
            window_from=window_from,
            window_to=window_to,
            window_open=period in _open_periods(org_houses, settings, now).values(),
            submitted=sum(house.submitted for house in houses),
            not_submitted=sum(house.not_submitted for house in houses),
            houses=houses,
            is_empty=not any(house.flats_total for house in houses),
        )

    async def remind_not_submitted(
        self,
        org_id: OrgId,
        house_ids: Sequence[HouseId],
        period: date | None,
        now: datetime,
    ) -> int:
        settings = await self._orgs.get_settings(org_id)
        if house_ids:
            await self._own_houses(org_id, house_ids)
            houses = await self._houses.list_by_ids(house_ids)
        else:
            houses = await self._houses.list_for_org(org_id)
        open_periods = _open_periods(houses, settings, now)
        if houses and not open_periods:
            raise InvalidState(WINDOW_CLOSED)
        if period is not None:
            open_periods = {
                house_id: current
                for house_id, current in open_periods.items()
                if current == period.replace(day=1)
            }
            if houses and not open_periods:
                raise InvalidRequest(WRONG_PERIOD)
        by_period: dict[date, list[HouseId]] = {}
        for house_id, current in open_periods.items():
            by_period.setdefault(current, []).append(house_id)
        sent = 0
        for current, ids in by_period.items():
            sent += await self._reminders.remind_reading_laggards(ids, current, now)
        return sent

    async def executors(
        self,
        org_id: OrgId,
        date_from: date | None,
        date_to: date | None,
        now: datetime,
    ) -> list[ExecutorRow]:
        org = await self._orgs.get_existing(org_id)
        period_from, period_to = _range(date_from, date_to, org.local(now))
        return await self._analytics.by_executor(
            org_id,
            org.day_start(period_from),
            org.day_start(period_to + timedelta(days=1)),
        )

    async def channels(
        self,
        org_id: OrgId,
        date_from: date | None,
        date_to: date | None,
        now: datetime,
    ) -> Channels:
        org = await self._orgs.get_existing(org_id)
        period_from, period_to = _range(date_from, date_to, org.local(now))
        rows = {
            row.channel: row
            for row in await self._analytics.by_channel(
                org_id,
                org.day_start(period_from),
                org.day_start(period_to + timedelta(days=1)),
            )
        }
        items = [
            rows.get(channel, ChannelRow(channel=channel, count=0, share=0))
            for channel in RequestChannel
        ]
        total = sum(item.count for item in items)
        return Channels(total=total, items=items, is_empty=total == 0)

    async def benchmark(self, org_id: OrgId, now: datetime) -> Benchmark:
        org = await self._orgs.get_existing(org_id)
        since = datetime.combine(now.date() - DEFAULT_PERIOD, time(), UTC)
        metrics = []
        for spec in BENCHMARK:
            rank = await self._analytics.org_rank(
                org_id,
                spec.metric,
                lower_is_better=spec.lower_is_better,
                is_demo=org.is_demo,
                since=since,
                now=now,
            )
            if rank is None:
                continue
            comparable = rank.total >= MIN_ORGS_FOR_CUT
            metrics.append(
                BenchmarkValue(
                    key=spec.metric.value,
                    label=spec.label,
                    unit=spec.unit,
                    value=rank.value,
                    platform_median=rank.median if comparable else None,
                    rank=rank.rank if comparable else None,
                    total=rank.total if comparable else None,
                ),
            )
        cuts = await self._analytics.cuts(
            CUT_METRIC.metric,
            is_demo=org.is_demo,
            min_orgs=MIN_ORGS_FOR_CUT,
            since=since,
            now=now,
        )
        unconnected = await self._analytics.unconnected_houses(UNCONNECTED_LIMIT)
        return Benchmark(
            metrics=metrics,
            regions=[
                RegionRow(
                    region=cut.region,
                    city=cut.city,
                    orgs_count=cut.orgs_count,
                    unit=CUT_METRIC.unit,
                    value=cut.value,
                )
                for cut in cuts
            ],
            unconnected_houses=[
                UnconnectedHouse(
                    house_id=house.id,
                    address=house.address,
                    waiting=waiting,
                )
                for house, waiting in unconnected
            ],
            is_empty=not (metrics or cuts or unconnected),
        )

    async def _own_houses(self, org_id: OrgId, house_ids: Sequence[HouseId]) -> None:
        if await self._houses.ids_for_org(house_ids, org_id) != set(house_ids):
            raise EntityNotFound(HOUSE_NOT_FOUND)


def _open_periods(
    houses: Sequence[House],
    settings: OrgSettings | None,
    now: datetime,
) -> dict[HouseId, date]:
    periods = {}
    for house in houses:
        today = house.local(now).date()
        if window_accepts(today, settings):
            periods[house.id] = window_period(today, settings)
    return periods
