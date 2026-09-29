from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, select

from zheka.infra.database.models import House, Organization
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.houses import houses_table
from zheka.infra.database.tables.organizations import organizations_table
from zheka.infra.database.tables.residents import demand_signals_table


class MapRepo(BaseAlchemyRepo):
    async def houses_in_box(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
    ) -> Sequence[tuple[House, Organization | None, int]]:
        demand = (
            select(func.count())
            .where(demand_signals_table.c.house_id == houses_table.c.id)
            .scalar_subquery()
        )
        stmt = (
            select(House, Organization, demand)
            .select_from(
                houses_table.outerjoin(
                    organizations_table,
                    organizations_table.c.id == houses_table.c.org_id,
                ),
            )
            .where(
                houses_table.c.lat.between(Decimal(str(south)), Decimal(str(north))),
                houses_table.c.lon.between(Decimal(str(west)), Decimal(str(east))),
            )
            .order_by(houses_table.c.id)
        )
        result = await self._session.execute(stmt)
        return result.tuples().all()
