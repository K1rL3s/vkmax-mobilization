from datetime import date

from sqlalchemy import select

from zheka.core.enums import ServiceType
from zheka.core.ids import FlatId, HouseId
from zheka.infra.database.models import Charge, Tariff
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.charges import charges_table, tariffs_table

# ChargesRepo принадлежит блоку 11 (тарифы и начисления); здесь только то,
# что нужно предварительному расчету при подаче показания - блок 11 разрастит
# репозиторий остальными методами


class ChargesRepo(BaseAlchemyRepo):
    async def tariff_at(
        self,
        house_id: HouseId,
        service: ServiceType,
        on: date,
    ) -> Tariff | None:
        stmt = (
            select(Tariff)
            .where(
                tariffs_table.c.house_id == house_id,
                tariffs_table.c.service == service,
                tariffs_table.c.valid_from <= on,
            )
            .order_by(tariffs_table.c.valid_from.desc())
            .limit(1)
        )
        tariff: Tariff | None = await self._session.scalar(stmt)
        return tariff

    async def get_by_period(self, flat_id: FlatId, period: date) -> Charge | None:
        stmt = select(Charge).where(
            charges_table.c.flat_id == flat_id,
            charges_table.c.period == period,
        )
        charge: Charge | None = await self._session.scalar(stmt)
        return charge
