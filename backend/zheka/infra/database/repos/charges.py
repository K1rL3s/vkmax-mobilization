from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from zheka.core.enums import ServiceType
from zheka.core.ids import ChargeId, FlatId, HouseId
from zheka.infra.database.models import Charge, Tariff
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.charges import charges_table, tariffs_table


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

    async def list_tariffs(self, house_id: HouseId) -> Sequence[Tariff]:
        stmt = (
            select(Tariff)
            .where(tariffs_table.c.house_id == house_id)
            .order_by(tariffs_table.c.valid_from.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_period(self, flat_id: FlatId, period: date) -> Charge | None:
        stmt = select(Charge).where(
            charges_table.c.flat_id == flat_id,
            charges_table.c.period == period,
        )
        charge: Charge | None = await self._session.scalar(stmt)
        return charge

    async def get(self, charge_id: ChargeId) -> Charge | None:
        stmt = select(Charge).where(charges_table.c.id == charge_id)
        charge: Charge | None = await self._session.scalar(stmt)
        return charge

    async def list_for_flat(
        self,
        flat_id: FlatId,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Charge], int]:
        stmt = select(Charge).where(charges_table.c.flat_id == flat_id)
        total = await self._count(stmt)
        page_stmt = (
            stmt.order_by(charges_table.c.period.desc()).limit(limit).offset(offset)
        )
        result = await self._session.execute(page_stmt)
        return result.scalars().all(), total

    async def mark_paid(self, charge: Charge, paid_at: datetime) -> None:
        charge.paid_at = paid_at
        await self._session.flush()

    async def add(
        self,
        flat_id: FlatId,
        period: date,
        lines: list[dict[str, Any]],
        total: int,
        created_at: datetime,
        paid_at: datetime | None,
    ) -> Charge:
        charge = Charge(
            flat_id=flat_id,
            period=period,
            lines=lines,
            total=total,
            created_at=created_at,
            paid_at=paid_at,
        )
        self._session.add(charge)
        await self._session.flush()
        return charge
