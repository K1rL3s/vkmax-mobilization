from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import (
    CurrentResidency,
    RequireConsentDep,
    ResidencyForFlatDep,
)
from zheka.api.schemas.files import FileRef
from zheka.api.schemas.meters import (
    AddMeterRequest,
    MeterItem,
    ReadingItem,
    ReadingPeriodItem,
    RecognizeReadingRequest,
    RecognizeReadingResponse,
    SubmitReadingRequest,
    SubmitReadingResponse,
    UpdateMeterRequest,
)
from zheka.core.errors import NotEnoughRights
from zheka.core.ids import FlatId, MeterId
from zheka.core.services.files import FilesService
from zheka.core.services.meter_access import NOT_VERIFIED
from zheka.core.services.meters import MeterDraft, MeterUpdateDraft, MetersService
from zheka.core.services.readings import ReadingRow, ReadingsService, SubmitDraft
from zheka.infra.yandex import VisionClient

router = APIRouter(tags=["Счетчики"], route_class=DishkaRoute)


def _require_verified(residency: CurrentResidency) -> None:
    if not residency.verified:
        raise NotEnoughRights(NOT_VERIFIED)


def _reading_item(row: ReadingRow, files_service: FilesService) -> ReadingItem:
    return ReadingItem(
        id=row.reading.id,
        meter_id=row.reading.meter_id,
        period=row.reading.period,
        values=row.values,
        consumption=row.consumption,
        photos=[
            FileRef.signed(name, files_service) for name in row.reading.photo_paths
        ],
        is_below_previous=row.reading.is_below_previous,
        ocr_used=row.reading.ocr_used,
        submitted_at=row.reading.submitted_at,
        amount=row.amount,
    )


@router.get("/flats/{flat_id}/meters", summary="Счетчики квартиры")
async def list_flat_meters(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    readings_service: FromDishka[ReadingsService],
) -> list[MeterItem]:
    _require_verified(residency)
    cards = await readings_service.list_meters(flat_id)
    return [MeterItem.of(card) for card in cards]


@router.get("/flats/{flat_id}/reading-periods", summary="Периоды подачи показаний")
async def list_reading_periods(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    readings_service: FromDishka[ReadingsService],
) -> list[ReadingPeriodItem]:
    _require_verified(residency)
    data = await readings_service.periods(flat_id)
    return [
        ReadingPeriodItem.of(option, is_submitted=option.period in data.submitted)
        for option in data.options
    ]


@router.get("/meters/{meter_id}/readings", summary="История показаний счетчика")
async def list_meter_readings(
    meter_id: MeterId,
    current_account: RequireConsentDep,
    readings_service: FromDishka[ReadingsService],
    files_service: FromDishka[FilesService],
) -> list[ReadingItem]:
    rows = await readings_service.history(current_account.user_id, meter_id)
    return [_reading_item(row, files_service) for row in rows]


@router.post("/meters/{meter_id}/readings", summary="Передать показание")
async def submit_reading(
    meter_id: MeterId,
    current_account: RequireConsentDep,
    readings_service: FromDishka[ReadingsService],
    files_service: FromDishka[FilesService],
    body: SubmitReadingRequest,
) -> SubmitReadingResponse:
    result = await readings_service.submit(
        current_account.user_id,
        meter_id,
        SubmitDraft(**body.model_dump()),
    )
    return SubmitReadingResponse(
        reading=_reading_item(result.row, files_service),
        house_average=result.house_average,
        warning=result.warning,
        suggested_category=result.suggested_category,
    )


@router.post("/meters/readings/recognize", summary="Распознать показание по фото")
async def recognize_reading(
    current_account: RequireConsentDep,  # noqa: ARG001
    vision_client: FromDishka[VisionClient],
    body: RecognizeReadingRequest,
) -> RecognizeReadingResponse:
    values = await vision_client.recognize(body.photo_path)
    return RecognizeReadingResponse(values=values)


@router.post("/flats/{flat_id}/meters", summary="Завести счетчик")
async def add_meter(
    flat_id: FlatId,
    current_account: RequireConsentDep,
    meters_service: FromDishka[MetersService],
    body: AddMeterRequest,
) -> MeterItem:
    card = await meters_service.add(
        current_account.user_id,
        flat_id,
        MeterDraft(**body.model_dump()),
    )
    return MeterItem.of(card)


@router.patch("/meters/{meter_id}", summary="Изменить счетчик")
async def update_meter(
    meter_id: MeterId,
    current_account: RequireConsentDep,
    meters_service: FromDishka[MetersService],
    body: UpdateMeterRequest,
) -> MeterItem:
    card = await meters_service.update(
        current_account.user_id,
        meter_id,
        MeterUpdateDraft(**body.model_dump()),
    )
    return MeterItem.of(card)
