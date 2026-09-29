from datetime import UTC, datetime
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Query

from zheka.api.dependencies import CurrentOrgDep
from zheka.api.schemas.admin_map import AdminMapResponse
from zheka.core.enums import HouseState, MapPeriod, RequestCategory
from zheka.core.services.admin_map import AdminMapFilters, AdminMapService

router = APIRouter(tags=["Админка: карта"], route_class=DishkaRoute)


@router.get("/admin/map/houses", summary="Дома организации на карте")
async def admin_map_houses(
    current_org: CurrentOrgDep,
    admin_map_service: FromDishka[AdminMapService],
    states: Annotated[list[HouseState] | None, Query()] = None,
    category: RequestCategory | None = None,
    period: MapPeriod = MapPeriod.MONTH,
    urgent: bool = False,
    poll: bool = False,
    reception_today: bool = False,
    meters_below: Annotated[
        int | None,
        Query(
            ge=0,
            le=100,
            description="Порог доли квартир, подавших показания, в целых процентах",
        ),
    ] = None,
    pending: bool = False,
) -> AdminMapResponse:
    data = await admin_map_service.houses(
        current_org.org_id,
        current_org.role.can_manage_houses,
        AdminMapFilters(
            states=frozenset(states or ()),
            category=category,
            period=period,
            urgent=urgent,
            poll=poll,
            reception_today=reception_today,
            meters_below=meters_below,
            pending=pending,
        ),
        datetime.now(UTC),
    )
    return AdminMapResponse.of(data)
