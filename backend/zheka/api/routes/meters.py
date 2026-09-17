from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import RequireConsentDep, ResidencyForFlatDep
from zheka.api.schemas.meters import (
    MeterItem,
    ReadingItem,
    ReadingPeriodItem,
    SubmitReadingRequest,
    SubmitReadingResponse,
)
from zheka.core.ids import FlatId, MeterId

router = APIRouter(tags=["Счетчики"], route_class=DishkaRoute)


@router.get("/flats/{flat_id}/meters", summary="Счетчики квартиры")
async def list_flat_meters(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
) -> list[MeterItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/flats/{flat_id}/reading-periods", summary="Периоды подачи показаний")
async def list_reading_periods(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
) -> list[ReadingPeriodItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/meters/{meter_id}/readings", summary="История показаний счетчика")
async def list_meter_readings(
    meter_id: MeterId,
    current_account: RequireConsentDep,
) -> list[ReadingItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post("/meters/{meter_id}/readings", summary="Передать показание")
async def submit_reading(
    meter_id: MeterId,
    current_account: RequireConsentDep,
    body: SubmitReadingRequest,
) -> SubmitReadingResponse:
    raise NotImplementedError("ещё не реализовано")
