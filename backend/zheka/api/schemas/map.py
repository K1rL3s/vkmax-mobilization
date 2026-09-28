from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import MapHouseKind
from zheka.core.ids import HouseId, OrgId
from zheka.core.services.map import MapData, MapHouseRow, MapOrgRow


class MapHouse(BaseSchema):
    id: HouseId
    lat: float
    lon: float
    building: str
    address: str
    kind: MapHouseKind
    is_demo: bool
    demand_count: int
    org_id: OrgId | None = None
    org_name: str | None = None
    on_time_share: int | None = Field(
        default=None,
        description="Доля заявок УК в срок за 90 дней, в сотых долях процента",
    )
    rating: int | None = Field(
        default=None,
        description="Средняя оценка УК за 90 дней, в сотых долях балла",
    )

    @classmethod
    def of(cls, row: MapHouseRow) -> Self:
        house = row.house
        return cls(
            id=house.id,
            lat=float(house.lat or 0),
            lon=float(house.lon or 0),
            building=house.building,
            address=house.address,
            kind=row.kind,
            is_demo=row.org is not None and row.org.is_demo,
            demand_count=row.demand_count,
            org_id=None if row.org is None else row.org.id,
            org_name=None if row.org is None else row.org.name,
            on_time_share=None if row.stats is None else row.stats.on_time_share,
            rating=None if row.stats is None else row.stats.rating,
        )


class MapOrg(BaseSchema):
    id: OrgId
    name: str
    is_demo: bool
    houses: int

    @classmethod
    def of(cls, row: MapOrgRow) -> Self:
        return cls(
            id=row.org.id,
            name=row.org.name,
            is_demo=row.org.is_demo,
            houses=row.houses,
        )


class MapHousesResponse(BaseSchema):
    items: list[MapHouse]
    total: int = Field(description="Сколько домов подходит под фильтры в рамке")
    orgs: list[MapOrg] = Field(description="Подключенные УК в рамке, без фильтра по УК")

    @classmethod
    def of(cls, data: MapData) -> Self:
        return cls(
            items=[MapHouse.of(row) for row in data.items],
            total=data.total,
            orgs=[MapOrg.of(row) for row in data.orgs],
        )
