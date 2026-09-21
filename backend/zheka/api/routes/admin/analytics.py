from datetime import UTC, date, datetime

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentOrgDep
from zheka.api.schemas.analytics import (
    BenchmarkResponse,
    ChannelsSplitResponse,
    DashboardResponse,
    ExecutorStatsItem,
    MetersSeasonResponse,
    RemindNotSubmittedRequest,
    RemindNotSubmittedResponse,
)
from zheka.core.ids import HouseId
from zheka.core.services.analytics import AnalyticsService

router = APIRouter(tags=["Админка: аналитика"], route_class=DishkaRoute)


@router.get("/admin/analytics/dashboard", summary="Дашборд организации")
async def get_dashboard(
    current_org: CurrentOrgDep,
    analytics_service: FromDishka[AnalyticsService],
    date_from: date | None = None,
    date_to: date | None = None,
    house_id: HouseId | None = None,
) -> DashboardResponse:
    dashboard = await analytics_service.dashboard(
        current_org.org_id,
        house_id,
        date_from,
        date_to,
        datetime.now(UTC),
    )
    return DashboardResponse.model_validate(dashboard)


@router.get("/admin/analytics/meters-season", summary="Сезон подачи показаний")
async def get_meters_season(
    current_org: CurrentOrgDep,
    analytics_service: FromDishka[AnalyticsService],
    period: date | None = None,
) -> MetersSeasonResponse:
    season = await analytics_service.season(
        current_org.org_id,
        period,
        datetime.now(UTC),
    )
    return MetersSeasonResponse.model_validate(season)


@router.post(
    "/admin/analytics/meters-season/remind",
    summary="Напомнить не сдавшим показания",
)
async def remind_not_submitted(
    current_org: CurrentOrgDep,
    body: RemindNotSubmittedRequest,
    analytics_service: FromDishka[AnalyticsService],
) -> RemindNotSubmittedResponse:
    queued = await analytics_service.remind_not_submitted(
        current_org.org_id,
        body.house_ids,
        body.period,
        datetime.now(UTC),
    )
    return RemindNotSubmittedResponse(queued=queued)


@router.get("/admin/analytics/executors", summary="Статистика по исполнителям")
async def get_executors_stats(
    current_org: CurrentOrgDep,
    analytics_service: FromDishka[AnalyticsService],
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[ExecutorStatsItem]:
    rows = await analytics_service.executors(
        current_org.org_id,
        date_from,
        date_to,
        datetime.now(UTC),
    )
    return [ExecutorStatsItem.model_validate(row) for row in rows]


@router.get("/admin/analytics/channels", summary="Заявки по каналам")
async def get_channels_split(
    current_org: CurrentOrgDep,
    analytics_service: FromDishka[AnalyticsService],
    date_from: date | None = None,
    date_to: date | None = None,
) -> ChannelsSplitResponse:
    channels = await analytics_service.channels(
        current_org.org_id,
        date_from,
        date_to,
        datetime.now(UTC),
    )
    return ChannelsSplitResponse.model_validate(channels)


@router.get("/admin/analytics/benchmark", summary="Обезличенный бенчмарк платформы")
async def get_benchmark(
    current_org: CurrentOrgDep,
    analytics_service: FromDishka[AnalyticsService],
) -> BenchmarkResponse:
    benchmark = await analytics_service.benchmark(
        current_org.org_id,
        datetime.now(UTC),
    )
    return BenchmarkResponse.model_validate(benchmark)
