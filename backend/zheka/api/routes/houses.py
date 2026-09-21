from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Query

from zheka.api.dependencies import RequireConsentDep, ResidencyForHouseDep
from zheka.api.schemas.base import Limit, Offset, OkResponse, Page
from zheka.api.schemas.files import FileRef
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
from zheka.core.services.files import FilesService
from zheka.core.services.houses import HousesService

router = APIRouter(tags=["Дома"], route_class=DishkaRoute)


@router.get("/geo/cities", summary="Города для поиска дома")
async def list_cities(
    current_account: RequireConsentDep,  # noqa: ARG001
    houses_service: FromDishka[HousesService],
    q: str | None = None,
    region: str | None = None,
) -> list[CityItem]:
    cities = await houses_service.cities(region, q)
    return [CityItem(region=region_, city=city) for region_, city in cities]


@router.get("/geo/streets", summary="Улицы города")
async def list_streets(
    current_account: RequireConsentDep,  # noqa: ARG001
    houses_service: FromDishka[HousesService],
    city: str,
    region: str | None = None,
    q: str | None = None,
) -> list[str]:
    return list(await houses_service.streets(city, region, q))


@router.get("/houses", summary="Поиск дома по адресу")
async def search_houses(
    current_account: RequireConsentDep,
    houses_service: FromDishka[HousesService],
    q: str | None = None,
    city: str | None = None,
    street: str | None = None,
    building: str | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[HouseListItem]:
    found, total = await houses_service.search(
        current_account.user_id, city, street, building, q, limit, offset
    )
    return Page(items=[HouseListItem.of(item) for item in found], total=total)


@router.get("/houses/nearby", summary="Дома рядом по геопозиции")
async def search_houses_nearby(
    current_account: RequireConsentDep,
    houses_service: FromDishka[HousesService],
    lat: float,
    lon: float,
    radius_m: Annotated[int, Query(ge=50, le=5000)] = 300,
    limit: Limit = 20,
) -> list[HouseListItem]:
    found = await houses_service.nearest(
        current_account.user_id, lat, lon, radius_m, limit
    )
    return [HouseListItem.of(item) for item in found]


@router.get("/houses/{house_id}", summary="Карточка дома")
async def get_house_card(
    house_id: HouseId,
    current_account: RequireConsentDep,
    houses_service: FromDishka[HousesService],
    files_service: FromDishka[FilesService],
) -> HouseCard:
    card = await houses_service.house_card(house_id, current_account.user_id)
    documents = [
        FileRef(name=name, url=files_service.sign(name))
        for name in card.house.documents
    ]
    return HouseCard.of(card, documents)


@router.post("/houses/{house_id}/link", summary="Привязать себя к дому")
async def link_house(
    house_id: HouseId,
    current_account: RequireConsentDep,
    houses_service: FromDishka[HousesService],
    body: LinkHouseRequest,
) -> ResidencySummary:
    view = await houses_service.link(
        current_account.user_id,
        house_id,
        body.flat_id,
        body.flat_number,
        body.role,
        body.source,
        body.entrance,
    )
    return ResidencySummary.of(view)


@router.delete("/residencies/{resident_id}", summary="Отвязаться от дома")
async def unlink_house(
    resident_id: ResidentId,
    current_account: RequireConsentDep,
    houses_service: FromDishka[HousesService],
) -> OkResponse:
    await houses_service.unlink(current_account.user_id, resident_id)
    return OkResponse()


@router.post("/houses/{house_id}/demand", summary="Сообщить о спросе на дом без УК")
async def create_demand_signal(
    house_id: HouseId,
    current_account: RequireConsentDep,
    houses_service: FromDishka[HousesService],
) -> DemandSignalResponse:
    total = await houses_service.demand_signal(current_account.user_id, house_id)
    return DemandSignalResponse(house_id=house_id, total=total)


@router.get("/houses/{house_id}/flats", summary="Квартиры дома")
async def list_house_flats(
    house_id: HouseId,
    residency: ResidencyForHouseDep,
    houses_service: FromDishka[HousesService],
    q: str | None = None,
    entrance: int | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[FlatListItem]:
    flats, total, taken = await houses_service.flats(
        residency.user_id, house_id, q, entrance, limit, offset
    )
    return Page(
        items=[FlatListItem.of(flat, flat.id in taken) for flat in flats], total=total
    )
