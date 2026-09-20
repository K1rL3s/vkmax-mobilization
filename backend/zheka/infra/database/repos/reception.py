from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, exists, func, select

from zheka.core.enums import AppointmentStatus
from zheka.core.ids import AppointmentId, HouseId, OrgId, RequestId, UserId
from zheka.infra.database.models import Appointment, ReceptionWindow
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.reception import (
    appointments_table,
    reception_windows_table,
)


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _day_end(day: date) -> datetime:
    return _day_start(day + timedelta(days=1))


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
        # часы приема задаются целиком: редактируется вся сетка кабинета, и
        # сведение старых строк с новыми стоило бы дороже полной замены
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
        on_date: date,
        house_id: HouseId | None,
    ) -> Sequence[Appointment]:
        stmt = select(Appointment).where(
            appointments_table.c.org_id == org_id,
            appointments_table.c.starts_at >= _day_start(on_date),
            appointments_table.c.starts_at < _day_end(on_date),
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
        date_from: date,
        date_to: date,
    ) -> dict[datetime, int]:
        # весь горизонт одним запросом: по запросу на день это четырнадцать
        # обращений к базе на одно открытие экрана
        stmt = (
            select(appointments_table.c.starts_at, func.count())
            .where(
                appointments_table.c.org_id == org_id,
                appointments_table.c.status == AppointmentStatus.BOOKED,
                appointments_table.c.starts_at >= _day_start(date_from),
                appointments_table.c.starts_at < _day_end(date_to),
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
        # места в слоте держит блокировка окон этого дня недели, а не
        # уникальный индекс: в слот помещается столько жителей, сколько в
        # кабинете сотрудников. Порядок по id - чтобы две одновременные записи
        # брали строки в одном порядке и не вставали в тупик.
        # Блокировка грубее слота - на весь день недели организации,
        # разбивать по слотам есть смысл только при очереди на запись
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
        # id приходит из пути, поэтому запрос сужается до записей жителя:
        # чужая запись отвечает 404, а не 403
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
        # запрос сужен организацией, как и блокировка окон, внутри которой он
        # выполняется: прием в двух кабинетах разом житель все равно не берет
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
