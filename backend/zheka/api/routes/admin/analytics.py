from datetime import date

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

router = APIRouter(tags=["Админка: аналитика"], route_class=DishkaRoute)


@router.get("/admin/analytics/dashboard", summary="Дашборд организации")
async def get_dashboard(
    current_org: CurrentOrgDep,
    date_from: date | None = None,
    date_to: date | None = None,
    house_id: HouseId | None = None,
) -> DashboardResponse:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/analytics/meters-season", summary="Сезон подачи показаний")
async def get_meters_season(
    current_org: CurrentOrgDep,
    period: date | None = None,
) -> MetersSeasonResponse:
    raise NotImplementedError("ещё не реализовано")


@router.post(
    "/admin/analytics/meters-season/remind",
    summary="Напомнить не сдавшим показания",
)
async def remind_not_submitted(
    current_org: CurrentOrgDep,
    body: RemindNotSubmittedRequest,
) -> RemindNotSubmittedResponse:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/analytics/executors", summary="Статистика по исполнителям")
async def get_executors_stats(
    current_org: CurrentOrgDep,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[ExecutorStatsItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/analytics/channels", summary="Заявки по каналам")
async def get_channels_split(
    current_org: CurrentOrgDep,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ChannelsSplitResponse:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/analytics/benchmark", summary="Обезличенный бенчмарк платформы")
async def get_benchmark(current_org: CurrentOrgDep) -> BenchmarkResponse:
    raise NotImplementedError("ещё не реализовано")
