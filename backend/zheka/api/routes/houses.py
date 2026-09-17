from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Query

from zheka.api.dependencies import RequireConsentDep
from zheka.api.schemas.base import Limit, Offset, OkResponse, Page
from zheka.api.schemas.houses import (
    CityItem,
    DemandSignalResponse,
    FlatListItem,
    HouseCard,
    HouseListItem,
    LinkHouseRequest,
    ResidencySummary,
)
from zheka.core.ids import HouseId, ResidentId

router = APIRouter(tags=["Дома"], route_class=DishkaRoute)


@router.get("/geo/cities", summary="Города для поиска дома")
async def list_cities(
    current_account: RequireConsentDep,
    q: str | None = None,
    region: str | None = None,
) -> list[CityItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/geo/streets", summary="Улицы города")
async def list_streets(
    current_account: RequireConsentDep,
    city: str,
    region: str | None = None,
    q: str | None = None,
) -> list[str]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/houses", summary="Поиск дома по адресу")
async def search_houses(
    current_account: RequireConsentDep,
    city: str,
    street: str | None = None,
    building: str | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[HouseListItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/houses/nearby", summary="Дома рядом по геопозиции")
async def search_houses_nearby(
    current_account: RequireConsentDep,
    lat: float,
    lon: float,
    radius_m: Annotated[int, Query(ge=50, le=5000)] = 300,
    limit: Limit = 20,
) -> list[HouseListItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/houses/{house_id}", summary="Карточка дома")
async def get_house_card(
    house_id: HouseId,
    current_account: RequireConsentDep,
) -> HouseCard:
    raise NotImplementedError("ещё не реализовано")


@router.post("/houses/{house_id}/link", summary="Привязать себя к дому")
async def link_house(
    house_id: HouseId,
    current_account: RequireConsentDep,
    body: LinkHouseRequest,
) -> ResidencySummary:
    raise NotImplementedError("ещё не реализовано")


@router.delete("/residencies/{resident_id}", summary="Отвязаться от дома")
async def unlink_house(
    resident_id: ResidentId,
    current_account: RequireConsentDep,
) -> OkResponse:
    raise NotImplementedError("ещё не реализовано")


@router.post("/houses/{house_id}/demand", summary="Сообщить о спросе на дом без УК")
async def create_demand_signal(
    house_id: HouseId,
    current_account: RequireConsentDep,
) -> DemandSignalResponse:
    raise NotImplementedError("ещё не реализовано")


@router.get("/houses/{house_id}/flats", summary="Квартиры дома")
async def list_house_flats(
    house_id: HouseId,
    current_account: RequireConsentDep,
    q: str | None = None,
    entrance: int | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[FlatListItem]:
    raise NotImplementedError("ещё не реализовано")
