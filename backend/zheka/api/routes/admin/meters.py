from datetime import date

from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentOrgDep
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.api.schemas.meters import AdminReadingItem
from zheka.core.enums import MeterType
from zheka.core.ids import HouseId

router = APIRouter(tags=["Админка: счетчики"], route_class=DishkaRoute)


@router.get("/admin/houses/{house_id}/readings", summary="Показания по дому")
async def list_house_readings(
    house_id: HouseId,
    current_org: CurrentOrgDep,
    period: date | None = None,
    meter_type: MeterType | None = None,
    only_below_previous: bool = False,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[AdminReadingItem]:
    raise NotImplementedError("ещё не реализовано")
