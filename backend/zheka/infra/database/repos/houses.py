from collections.abc import Collection, Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, exists, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.ids import FlatId, HouseId, OrgId, UserId
from zheka.infra.database.models import DemandSignal, Flat, House
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.chats import chats_table
from zheka.infra.database.tables.houses import flats_table, houses_table
from zheka.infra.database.tables.residents import demand_signals_table


class HousesRepo(BaseAlchemyRepo):
    async def get(self, house_id: HouseId) -> House | None:
        stmt = select(House).where(houses_table.c.id == house_id)
        # аннотация обязательна: House отображен императивно, и scalar()
        # для такой сущности возвращает Any
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
        city: str,
        street: str | None,
        building: str | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[House], int]:
        stmt = select(House).where(houses_table.c.city == city)
        if street is not None:
            stmt = stmt.where(houses_table.c.street == street)
        if building is not None:
            stmt = stmt.where(houses_table.c.building.ilike(f"{building}%"))

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
        # квадрат расстояния в градусах широты: без PostGIS и без корня в базе,
        # порядок сортировки от возведения в квадрат не меняется. Градус
        # долготы короче градуса широты в cos(широты) раз, и без этого
        # множителя радиус превращается в эллипс, вытянутый по долготе
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
        self,
        region: str | None,
        query: str | None,
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
        self,
        city: str,
        region: str | None,
        query: str | None,
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
        # идемпотентность держит уникальный индекс (house_id, user_id),
        # а не чтение перед записью: два параллельных запроса прошли бы его оба
        stmt = (
            pg_insert(DemandSignal)
            .values(house_id=house_id, user_id=user_id)
            .on_conflict_do_nothing(
                index_elements=[
                    demand_signals_table.c.house_id,
                    demand_signals_table.c.user_id,
                ],
            )
        )
        await self._session.execute(stmt)

    async def has_demand_signal(self, house_id: HouseId, user_id: UserId) -> bool:
        stmt = select(
            exists().where(
                demand_signals_table.c.house_id == house_id,
                demand_signals_table.c.user_id == user_id,
            ),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def is_chat_bound(self, house_id: HouseId) -> bool:
        stmt = select(
            exists().where(
                chats_table.c.house_id == house_id,
                chats_table.c.bound_at.is_not(None),
            ),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def _count(self, stmt: Select[Any]) -> int:
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await self._session.execute(count_stmt)
        return result.scalar_one()
