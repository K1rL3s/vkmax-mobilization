from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, exists, func, select

from zheka.core.enums import AppointmentStatus
from zheka.core.ids import AppointmentId, HouseId, OrgId, RequestId, UserId
from zheka.infra.database.models import Appointment, ReceptionWindow
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.reception import (
    appointments_table,
    reception_windows_table,
)


class ReceptionRepo(BaseAlchemyRepo):
    async def list_windows(self, org_id: OrgId) -> Sequence[ReceptionWindow]:
        stmt = (
            select(ReceptionWindow)
            .where(reception_windows_table.c.org_id == org_id)
            .order_by(
                reception_windows_table.c.weekday,
                reception_windows_table.c.time_from,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def replace_windows(
        self,
        org_id: OrgId,
        windows: Sequence[ReceptionWindow],
    ) -> Sequence[ReceptionWindow]:
        stmt = delete(reception_windows_table).where(
            reception_windows_table.c.org_id == org_id,
        )
        await self._session.execute(stmt)
        self._session.add_all(windows)
        await self._session.flush()
        return windows

    async def list_appointments(
        self,
        org_id: OrgId,
        since: datetime,
        until: datetime,
        house_id: HouseId | None,
    ) -> Sequence[Appointment]:
        stmt = select(Appointment).where(
            appointments_table.c.org_id == org_id,
            appointments_table.c.starts_at >= since,
            appointments_table.c.starts_at < until,
        )
        if house_id is not None:
            stmt = stmt.where(appointments_table.c.house_id == house_id)
        stmt = stmt.order_by(appointments_table.c.starts_at)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_user(self, user_id: UserId) -> Sequence[Appointment]:
        stmt = (
            select(Appointment)
            .where(appointments_table.c.user_id == user_id)
            .order_by(appointments_table.c.starts_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def taken_counts(
        self,
        org_id: OrgId,
        since: datetime,
        until: datetime,
    ) -> dict[datetime, int]:
        stmt = (
            select(appointments_table.c.starts_at, func.count())
            .where(
                appointments_table.c.org_id == org_id,
                appointments_table.c.status == AppointmentStatus.BOOKED,
                appointments_table.c.starts_at >= since,
                appointments_table.c.starts_at < until,
            )
            .group_by(appointments_table.c.starts_at)
        )
        result = await self._session.execute(stmt)
        return dict(result.tuples().all())

    async def lock_windows(
        self,
        org_id: OrgId,
        weekday: int,
    ) -> Sequence[ReceptionWindow]:
        stmt = (
            select(ReceptionWindow)
            .where(
                reception_windows_table.c.org_id == org_id,
                reception_windows_table.c.weekday == weekday,
            )
            .order_by(reception_windows_table.c.id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_booked(self, org_id: OrgId, starts_at: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(appointments_table)
            .where(
                appointments_table.c.org_id == org_id,
                appointments_table.c.starts_at == starts_at,
                appointments_table.c.status == AppointmentStatus.BOOKED,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create_appointment(
        self,
        org_id: OrgId,
        house_id: HouseId,
        user_id: UserId,
        starts_at: datetime,
        request_id: RequestId | None,
    ) -> Appointment:
        appointment = Appointment(
            org_id=org_id,
            house_id=house_id,
            user_id=user_id,
            request_id=request_id,
            starts_at=starts_at,
            status=AppointmentStatus.BOOKED,
        )
        self._session.add(appointment)
        await self._session.flush()
        return appointment

    async def get_for_user(
        self,
        appointment_id: AppointmentId,
        user_id: UserId,
    ) -> Appointment | None:
        stmt = select(Appointment).where(
            appointments_table.c.id == appointment_id,
            appointments_table.c.user_id == user_id,
        )
        appointment: Appointment | None = await self._session.scalar(stmt)
        return appointment

    async def cancel_appointment(self, appointment: Appointment) -> None:
        appointment.status = AppointmentStatus.CANCELLED
        await self._session.flush()

    async def has_booking(
        self,
        org_id: OrgId,
        user_id: UserId,
        starts_at: datetime,
    ) -> bool:
        stmt = select(
            exists().where(
                appointments_table.c.org_id == org_id,
                appointments_table.c.user_id == user_id,
                appointments_table.c.starts_at == starts_at,
                appointments_table.c.status == AppointmentStatus.BOOKED,
            ),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def list_to_remind(
        self,
        since: datetime,
        until: datetime,
    ) -> Sequence[Appointment]:
        stmt = select(Appointment).where(
            appointments_table.c.status == AppointmentStatus.BOOKED,
            appointments_table.c.reminder_sent_at.is_(None),
            appointments_table.c.starts_at >= since,
            appointments_table.c.starts_at < until,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def mark_reminded(self, appointment: Appointment, at: datetime) -> None:
        appointment.reminder_sent_at = at
        await self._session.flush()
