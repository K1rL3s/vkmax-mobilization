from collections.abc import Collection, Mapping, Sequence
from datetime import date, datetime

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import MeterType, TariffZone
from zheka.core.ids import FlatId, HouseId, MeterId, UserId
from zheka.infra.database.models import Meter, Reading
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.houses import flats_table
from zheka.infra.database.tables.meters import meters_table, readings_table


class MetersRepo(BaseAlchemyRepo):
    async def list_for_flat(self, flat_id: FlatId) -> Sequence[Meter]:
        stmt = (
            select(Meter)
            .where(meters_table.c.flat_id == flat_id)
            .order_by(meters_table.c.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get(self, meter_id: MeterId) -> Meter | None:
        stmt = select(Meter).where(meters_table.c.id == meter_id)
        meter: Meter | None = await self._session.scalar(stmt)
        return meter

    async def list_by_ids(self, meter_ids: Collection[MeterId]) -> Sequence[Meter]:
        if not meter_ids:
            return []
        stmt = select(Meter).where(meters_table.c.id.in_(meter_ids))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add(
        self,
        flat_id: FlatId,
        type: MeterType,
        tariff_zones: int,
        serial: str,
        next_verification_date: date | None,
    ) -> Meter | None:
        stmt = (
            pg_insert(Meter)
            .values(
                flat_id=flat_id,
                type=type,
                tariff_zones=tariff_zones,
                serial=serial,
                next_verification_date=next_verification_date,
            )
            .on_conflict_do_nothing(
                index_elements=[meters_table.c.flat_id, meters_table.c.type],
            )
            .returning(Meter)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        meter: Meter,
        tariff_zones: int,
        serial: str,
        next_verification_date: date | None,
    ) -> None:
        meter.tariff_zones = tariff_zones
        meter.serial = serial
        meter.next_verification_date = next_verification_date
        await self._session.flush()

    async def latest_reading(self, meter_id: MeterId, period: date) -> Reading | None:
        stmt = (
            select(Reading)
            .where(
                readings_table.c.meter_id == meter_id,
                readings_table.c.period == period,
            )
            .order_by(readings_table.c.submitted_at.desc())
            .limit(1)
        )
        reading: Reading | None = await self._session.scalar(stmt)
        return reading

    async def previous_reading(self, meter_id: MeterId, period: date) -> Reading | None:
        stmt = (
            select(Reading)
            .where(
                readings_table.c.meter_id == meter_id,
                readings_table.c.period < period,
            )
            .order_by(
                readings_table.c.period.desc(),
                readings_table.c.submitted_at.desc(),
            )
            .limit(1)
        )
        reading: Reading | None = await self._session.scalar(stmt)
        return reading

    async def list_readings(self, meter_id: MeterId, limit: int) -> Sequence[Reading]:
        stmt = (
            select(Reading)
            .where(readings_table.c.meter_id == meter_id)
            .order_by(readings_table.c.submitted_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add_reading(
        self,
        meter_id: MeterId,
        period: date,
        values: Mapping[TariffZone, int],
        photo_paths: Sequence[str],
        *,
        ocr_used: bool,
        ocr_accepted: bool,
        is_below_previous: bool,
        submitted_at: datetime,
        submitted_by: UserId,
    ) -> Reading:
        reading = Reading(
            meter_id=meter_id,
            period=period,
            values=dict(values),
            photo_paths=list(photo_paths),
            ocr_used=ocr_used,
            ocr_accepted=ocr_accepted,
            is_below_previous=is_below_previous,
            submitted_at=submitted_at,
            submitted_by=submitted_by,
        )
        self._session.add(reading)
        await self._session.flush()
        return reading

    async def list_house_readings(
        self,
        house_id: HouseId,
        *,
        period: date | None,
        meter_type: MeterType | None,
        limit: int,
        only_below_previous: bool = False,
        offset: int = 0,
    ) -> tuple[Sequence[Reading], int]:
        stmt = (
            select(Reading)
            .join(meters_table, meters_table.c.id == readings_table.c.meter_id)
            .join(flats_table, flats_table.c.id == meters_table.c.flat_id)
            .where(flats_table.c.house_id == house_id)
        )
        if period is not None:
            stmt = stmt.where(readings_table.c.period == period)
        if meter_type is not None:
            stmt = stmt.where(meters_table.c.type == meter_type)
        if only_below_previous:
            stmt = stmt.where(readings_table.c.is_below_previous.is_(True))

        total = await self._count(stmt)
        page_stmt = (
            stmt.order_by(readings_table.c.submitted_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(page_stmt)
        return result.scalars().all(), total

    async def flats_without_reading(
        self,
        house_id: HouseId,
        period: date,
    ) -> Sequence[FlatId]:
        has_meter = select(meters_table.c.flat_id).distinct()
        submitted = (
            select(meters_table.c.flat_id)
            .join(readings_table, readings_table.c.meter_id == meters_table.c.id)
            .where(readings_table.c.period == period)
            .distinct()
        )
        stmt = (
            select(flats_table.c.id)
            .where(
                flats_table.c.house_id == house_id,
                flats_table.c.id.in_(has_meter),
                flats_table.c.id.not_in(submitted),
            )
            .order_by(flats_table.c.id)
        )
        result = await self._session.execute(stmt)
        return [FlatId(flat_id) for flat_id in result.scalars().all()]

    async def list_to_warn(self, until: date) -> Sequence[Meter]:
        stmt = (
            select(Meter)
            .where(
                meters_table.c.next_verification_date <= until,
                or_(
                    meters_table.c.verification_warned_at.is_(None),
                    meters_table.c.verification_warned_at
                    < meters_table.c.next_verification_date,
                ),
            )
            .order_by(meters_table.c.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def mark_warned(self, meter: Meter, on: date) -> None:
        meter.verification_warned_at = on
        await self._session.flush()
