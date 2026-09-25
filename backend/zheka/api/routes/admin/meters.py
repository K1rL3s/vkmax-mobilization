from datetime import date

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentOrgDep
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.api.schemas.files import FileRef
from zheka.api.schemas.meters import AdminReadingItem
from zheka.core.enums import MeterType
from zheka.core.ids import HouseId
from zheka.core.services.admin_readings import AdminReadingRow, AdminReadingsService
from zheka.core.services.files import FilesService

router = APIRouter(tags=["Админка: счетчики"], route_class=DishkaRoute)


def _admin_item(row: AdminReadingRow, files_service: FilesService) -> AdminReadingItem:
    return AdminReadingItem(
        id=row.reading.id,
        meter_id=row.reading.meter_id,
        meter_type=row.meter.type,
        serial=row.meter.serial,
        flat_id=row.meter.flat_id,
        flat_number=row.flat_number,
        period=row.reading.period,
        values=row.values,
        consumption=row.consumption,
        photos=[
            FileRef.signed(name, files_service) for name in row.reading.photo_paths
        ],
        is_below_previous=row.reading.is_below_previous,
        ocr_used=row.reading.ocr_used,
        submitted_at=row.reading.submitted_at,
        submitted_by_name=row.submitted_by.name,
    )


@router.get("/admin/houses/{house_id}/readings", summary="Показания по дому")
async def list_house_readings(
    house_id: HouseId,
    current_org: CurrentOrgDep,
    admin_readings_service: FromDishka[AdminReadingsService],
    files_service: FromDishka[FilesService],
    period: date | None = None,
    meter_type: MeterType | None = None,
    only_below_previous: bool = False,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[AdminReadingItem]:
    rows, total = await admin_readings_service.admin_list(
        current_org.org_id,
        house_id,
        period,
        meter_type,
        only_below_previous=only_below_previous,
        limit=limit,
        offset=offset,
    )
    return Page(items=[_admin_item(row, files_service) for row in rows], total=total)
