from datetime import date

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import MetricUnit, RequestChannel
from zheka.core.ids import HouseId, UserId

_PERCENT = "Доля в сотых долях процента, 50% это 5000"
_VALUE = (
    "Целое в единицах unit: count без масштаба, minutes в минутах, "
    "percent в сотых долях процента, kopeck в копейках"
)


class DashboardTile(BaseSchema):
    key: str
    label: str
    unit: MetricUnit
    value: int = Field(description=_VALUE)
    delta_percent: int | None = Field(default=None, description=_PERCENT)


class ChartPoint(BaseSchema):
    label: str
    value: int = Field(description=_VALUE)


class ChartSeries(BaseSchema):
    key: str
    title: str
    unit: MetricUnit
    points: list[ChartPoint]


class DashboardResponse(BaseSchema):
    period_from: date
    period_to: date
    tiles: list[DashboardTile]
    charts: list[ChartSeries]


class MetersSeasonHouse(BaseSchema):
    house_id: HouseId
    address: str
    flats_total: int
    submitted: int
    not_submitted: int
    percent: int = Field(description=_PERCENT)


class MetersSeasonResponse(BaseSchema):
    period: date
    window_from: date
    window_to: date
    submitted: int
    not_submitted: int
    houses: list[MetersSeasonHouse]


class RemindNotSubmittedRequest(BaseSchema):
    period: date | None = None
    house_ids: list[HouseId] = Field(default_factory=list)


class RemindNotSubmittedResponse(BaseSchema):
    queued: int


class ExecutorStatsItem(BaseSchema):
    user_id: UserId
    name: str
    closed: int
    repeat_share: int = Field(description=_PERCENT)
    median_time: int | None = Field(
        default=None,
        description="Медианное время закрытия в минутах",
    )
    rating: int | None = Field(
        default=None,
        description="Средняя оценка в сотых долях балла",
    )


class ChannelSplitItem(BaseSchema):
    channel: RequestChannel
    count: int
    share: int = Field(description=_PERCENT)


class ChannelsSplitResponse(BaseSchema):
    total: int
    items: list[ChannelSplitItem]


class BenchmarkMetric(BaseSchema):
    key: str
    label: str
    unit: MetricUnit
    value: int = Field(description=_VALUE)
    platform_median: int = Field(description=_VALUE)
    rank: int
    total: int


class BenchmarkRegionRow(BaseSchema):
    region: str
    orgs_count: int
    unit: MetricUnit
    value: int = Field(description=_VALUE)
    city: str | None = None


class UnconnectedHouseItem(BaseSchema):
    house_id: HouseId
    address: str
    waiting: int


class BenchmarkResponse(BaseSchema):
    metrics: list[BenchmarkMetric]
    regions: list[BenchmarkRegionRow]
    unconnected_houses: list[UnconnectedHouseItem]
