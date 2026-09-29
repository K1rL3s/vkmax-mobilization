from datetime import UTC, datetime
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Query

from zheka.api.dependencies import RequireConsentDep
from zheka.api.schemas.map import MapHousesResponse
from zheka.core.enums import MapHouseKind
from zheka.core.ids import OrgId
from zheka.core.services.map import MAP_LIMIT, Box, MapFilters, MapService

router = APIRouter(tags=["Карта"], route_class=DishkaRoute)

Longitude = Annotated[float, Query(ge=-180, le=180)]
Latitude = Annotated[float, Query(ge=-90, le=90)]
Share = Annotated[int | None, Query(ge=0, le=10_000)]
Rating = Annotated[int | None, Query(ge=0, le=500)]


@router.get("/map/houses", summary="Дома в рамке карты")
async def map_houses(
    current_account: RequireConsentDep,  # noqa: ARG001
    map_service: FromDishka[MapService],
    west: Longitude,
    south: Latitude,
    east: Longitude,
    north: Latitude,
    kinds: Annotated[list[MapHouseKind] | None, Query()] = None,
    org_ids: Annotated[list[OrgId] | None, Query()] = None,
    waiting: bool = False,
    on_time_from: Share = None,
    on_time_to: Share = None,
    rating_from: Rating = None,
    rating_to: Rating = None,
    limit: Annotated[int, Query(ge=1, le=MAP_LIMIT)] = MAP_LIMIT,
) -> MapHousesResponse:
    data = await map_service.houses(
        Box(west=west, south=south, east=east, north=north),
        MapFilters(
            kinds=frozenset(kinds or ()),
            org_ids=frozenset(org_ids or ()),
            waiting=waiting,
            on_time_from=on_time_from,
            on_time_to=on_time_to,
            rating_from=rating_from,
            rating_to=rating_to,
            limit=limit,
        ),
        datetime.now(UTC),
    )
    return MapHousesResponse.of(data)
