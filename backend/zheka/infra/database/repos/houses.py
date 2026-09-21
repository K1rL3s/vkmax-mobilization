from collections.abc import Collection, Sequence
from decimal import Decimal

from sqlalchemy import exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import RequestStatus
from zheka.core.errors import EntityNotFound
from zheka.core.ids import FlatId, HouseId, OrgId, UserId
from zheka.infra.database.models import DemandSignal, Flat, House, OrgSettings
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.repos.chats import BOUND_CHAT
from zheka.infra.database.repos.scopes import scoped_to_org
from zheka.infra.database.tables.chats import chats_table
from zheka.infra.database.tables.houses import flats_table, houses_table
from zheka.infra.database.tables.organizations import org_settings_table
from zheka.infra.database.tables.requests import requests_table
from zheka.infra.database.tables.residents import demand_signals_table


class HousesRepo(BaseAlchemyRepo):
    async def get(self, house_id: HouseId) -> House | None:
        stmt = select(House).where(houses_table.c.id == house_id)
        house: House | None = await self._session.scalar(stmt)
        return house

    async def list_by_ids(self, house_ids: Collection[HouseId]) -> Sequence[House]:
        if not house_ids:
            return []
        stmt = select(House).where(houses_table.c.id.in_(house_ids))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_org(self, org_id: OrgId) -> Sequence[House]:
        stmt = (
            select(House)
            .where(houses_table.c.org_id == org_id)
            .order_by(houses_table.c.street, houses_table.c.building)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def search(
        self,
        city: str | None,
        street: str | None,
        building: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[House], int]:
        stmt = select(House)
        if city is not None:
            stmt = stmt.where(houses_table.c.city == city)
        if street is not None:
            stmt = stmt.where(houses_table.c.street == street)
        if building is not None:
            stmt = stmt.where(houses_table.c.building.ilike(f"{building}%"))
        if query is not None:
            address = func.concat_ws(
                " ", houses_table.c.city, houses_table.c.street, houses_table.c.building
            )
            for word in query.split():
                stmt = stmt.where(address.ilike(f"%{word}%"))

        total = await self._count(stmt)
        page_stmt = (
            stmt.order_by(houses_table.c.street, houses_table.c.building)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(page_stmt)
        return result.scalars().all(), total

    async def nearest(
        self,
        lat: Decimal,
        lon: Decimal,
        lon_scale: Decimal,
        radius_degrees: Decimal,
        limit: int,
    ) -> Sequence[tuple[House, Decimal]]:
        lat_delta = houses_table.c.lat - lat
        lon_delta = (houses_table.c.lon - lon) * lon_scale
        distance = lat_delta * lat_delta + lon_delta * lon_delta
        stmt = (
            select(House, distance.label("distance"))
            .where(
                houses_table.c.lat.is_not(None),
                houses_table.c.lon.is_not(None),
                distance <= radius_degrees * radius_degrees,
            )
            .order_by(distance)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.tuples().all()

    async def list_cities(
        self, region: str | None, query: str | None
    ) -> Sequence[tuple[str, str]]:
        stmt = select(houses_table.c.region, houses_table.c.city).distinct()
        if region is not None:
            stmt = stmt.where(houses_table.c.region == region)
        if query is not None:
            stmt = stmt.where(houses_table.c.city.ilike(f"{query}%"))
        stmt = stmt.order_by(houses_table.c.region, houses_table.c.city)
        result = await self._session.execute(stmt)
        return result.tuples().all()

    async def list_streets(
        self, city: str, region: str | None, query: str | None
    ) -> Sequence[str]:
        stmt = (
            select(houses_table.c.street).distinct().where(houses_table.c.city == city)
        )
        if region is not None:
            stmt = stmt.where(houses_table.c.region == region)
        if query is not None:
            stmt = stmt.where(houses_table.c.street.ilike(f"{query}%"))
        stmt = stmt.order_by(houses_table.c.street)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_flat(self, flat_id: FlatId) -> Flat | None:
        stmt = select(Flat).where(flats_table.c.id == flat_id)
        flat: Flat | None = await self._session.scalar(stmt)
        return flat

    async def get_flat_by_number(self, house_id: HouseId, number: str) -> Flat | None:
        stmt = select(Flat).where(
            flats_table.c.house_id == house_id,
            func.lower(flats_table.c.number) == number.lower(),
        )
        flat: Flat | None = await self._session.scalar(stmt)
        return flat

    async def list_flats_by_ids(self, flat_ids: Collection[FlatId]) -> Sequence[Flat]:
        if not flat_ids:
            return []
        stmt = select(Flat).where(flats_table.c.id.in_(flat_ids))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_flats(
        self,
        house_id: HouseId,
        query: str | None,
        entrance: int | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Flat], int]:
        stmt = select(Flat).where(flats_table.c.house_id == house_id)
        if query is not None:
            stmt = stmt.where(flats_table.c.number.ilike(f"{query}%"))
        if entrance is not None:
            stmt = stmt.where(flats_table.c.entrance == entrance)

        total = await self._count(stmt)
        page_stmt = stmt.order_by(flats_table.c.number).limit(limit).offset(offset)
        result = await self._session.execute(page_stmt)
        return result.scalars().all(), total

    async def count_demand(self, house_id: HouseId) -> int:
        stmt = (
            select(func.count())
            .select_from(demand_signals_table)
            .where(demand_signals_table.c.house_id == house_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def add_demand_signal(self, house_id: HouseId, user_id: UserId) -> None:
        stmt = (
            pg_insert(DemandSignal)
            .values(house_id=house_id, user_id=user_id)
            .on_conflict_do_nothing(
                index_elements=[
                    demand_signals_table.c.house_id,
                    demand_signals_table.c.user_id,
                ]
            )
        )
        await self._session.execute(stmt)

    async def has_demand_signal(self, house_id: HouseId, user_id: UserId) -> bool:
        stmt = select(
            exists().where(
                demand_signals_table.c.house_id == house_id,
                demand_signals_table.c.user_id == user_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def is_chat_bound(self, house_id: HouseId) -> bool:
        stmt = select(exists().where(chats_table.c.house_id == house_id, BOUND_CHAT))
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_for_org(self, house_id: HouseId, org_id: OrgId) -> House | None:
        stmt = select(House).where(
            houses_table.c.id == house_id, houses_table.c.org_id == org_id
        )
        house: House | None = await self._session.scalar(stmt)
        return house

    async def search_for_org(
        self, org_id: OrgId, query: str | None, limit: int, offset: int
    ) -> tuple[Sequence[House], int]:
        stmt = select(House).where(houses_table.c.org_id == org_id)
        if query is not None:
            stmt = stmt.where(
                or_(
                    houses_table.c.street.ilike(f"%{query}%"),
                    houses_table.c.building.ilike(f"{query}%"),
                )
            )

        total = await self._count(stmt)
        page_stmt = (
            stmt.order_by(houses_table.c.street, houses_table.c.building)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(page_stmt)
        return result.scalars().all(), total

    async def count_flats_by_house(
        self, house_ids: Collection[HouseId]
    ) -> dict[HouseId, int]:
        if not house_ids:
            return {}
        stmt = (
            select(flats_table.c.house_id, func.count())
            .where(flats_table.c.house_id.in_(house_ids))
            .group_by(flats_table.c.house_id)
        )
        result = await self._session.execute(stmt)
        return {HouseId(house_id): count for house_id, count in result.tuples().all()}

    async def count_open_requests_by_house(
        self, house_ids: Collection[HouseId]
    ) -> dict[HouseId, int]:
        if not house_ids:
            return {}
        stmt = (
            select(requests_table.c.house_id, func.count())
            .where(
                requests_table.c.house_id.in_(house_ids),
                requests_table.c.status != RequestStatus.DONE,
            )
            .group_by(requests_table.c.house_id)
        )
        result = await self._session.execute(stmt)
        return {HouseId(house_id): count for house_id, count in result.tuples().all()}

    async def bound_chat_titles(
        self, house_ids: Collection[HouseId]
    ) -> dict[HouseId, str | None]:
        if not house_ids:
            return {}
        stmt = select(chats_table.c.house_id, chats_table.c.title).where(
            chats_table.c.house_id.in_(house_ids), BOUND_CHAT
        )
        result = await self._session.execute(stmt)
        return {HouseId(house_id): title for house_id, title in result.tuples().all()}

    async def set_binding_code(self, house: House, code: str) -> None:
        house.chat_binding_code = code
        await self._session.flush()

    async def ids_for_org(
        self, house_ids: Collection[HouseId], org_id: OrgId
    ) -> set[HouseId]:
        if not house_ids:
            return set()
        stmt = scoped_to_org(
            select(houses_table.c.id).where(houses_table.c.id.in_(house_ids)),
            houses_table.c.id,
            org_id,
        )
        result = await self._session.execute(stmt)
        return {HouseId(house_id) for house_id in result.scalars().all()}

    async def get_by_binding_code(self, code: str) -> House | None:
        stmt = select(House).where(houses_table.c.chat_binding_code == code)
        house: House | None = await self._session.scalar(stmt)
        return house

    async def list_managed_with_settings(
        self,
    ) -> Sequence[tuple[HouseId, OrgSettings | None]]:
        stmt = (
            select(houses_table.c.id, OrgSettings)
            .select_from(
                houses_table.outerjoin(
                    org_settings_table,
                    org_settings_table.c.org_id == houses_table.c.org_id,
                )
            )
            .where(houses_table.c.org_id.is_not(None))
            .order_by(houses_table.c.id)
        )
        result = await self._session.execute(stmt)
        return [
            (HouseId(house_id), settings)
            for house_id, settings in result.tuples().all()
        ]

    async def add_flat_or_get(
        self, house_id: HouseId, number: str, area: int | None, account_no: str | None
    ) -> tuple[Flat, bool]:
        stmt = (
            pg_insert(Flat)
            .values(house_id=house_id, number=number, area=area, account_no=account_no)
            .on_conflict_do_nothing(
                index_elements=[flats_table.c.house_id, flats_table.c.number]
            )
            .returning(Flat)
        )
        result = await self._session.execute(stmt)
        created = result.scalar_one_or_none()
        if created is not None:
            return created, True
        flat = await self.get_flat_by_number(house_id, number)
        if flat is None:
            raise EntityNotFound("Квартира не найдена")
        return flat, False
