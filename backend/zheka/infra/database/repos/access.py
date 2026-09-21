from collections.abc import Collection, Sequence
from datetime import date, datetime

from sqlalchemy import func, select

from zheka.core.ids import (
    AccessRequestId,
    AccessSlotId,
    FlatId,
    HouseId,
    OrgId,
    UserId,
)
from zheka.infra.database.models import AccessRequest, AccessSlot, AccessTarget
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.repos.scopes import scoped_to_org
from zheka.infra.database.tables.access import (
    access_requests_table,
    access_slots_table,
    access_targets_table,
)


class AccessRepo(BaseAlchemyRepo):
    async def create_request(
        self,
        org_id: OrgId,
        house_id: HouseId,
        reason: str,
        on_date: date,
        created_by: UserId,
    ) -> AccessRequest:
        request = AccessRequest(
            org_id=org_id,
            house_id=house_id,
            reason=reason,
            date=on_date,
            created_by=created_by,
        )
        self._session.add(request)
        await self._session.flush()
        return request

    async def get(self, access_request_id: AccessRequestId) -> AccessRequest:
        stmt = select(AccessRequest).where(
            access_requests_table.c.id == access_request_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_for_org(
        self,
        access_request_id: AccessRequestId,
        org_id: OrgId,
    ) -> AccessRequest | None:
        # id приходит из пути, поэтому запрос сужается до домов организации:
        # чужой запрос отвечает 404, а не 403
        stmt = scoped_to_org(
            select(AccessRequest).where(
                access_requests_table.c.id == access_request_id,
            ),
            access_requests_table.c.house_id,
            org_id,
        )
        request: AccessRequest | None = await self._session.scalar(stmt)
        return request

    async def list_for_org(
        self,
        org_id: OrgId,
        house_id: HouseId | None,
    ) -> Sequence[AccessRequest]:
        stmt = select(AccessRequest).where(access_requests_table.c.org_id == org_id)
        if house_id is not None:
            stmt = stmt.where(access_requests_table.c.house_id == house_id)
        stmt = stmt.order_by(access_requests_table.c.id.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_flat(
        self,
        flat_id: FlatId,
    ) -> Sequence[tuple[AccessRequest, AccessTarget]]:
        # запрос и своя ячейка в нем одним запросом: без нее жителю нечего
        # подсветить в списке
        stmt = (
            select(AccessRequest, AccessTarget)
            .join(
                access_targets_table,
                access_targets_table.c.access_request_id == access_requests_table.c.id,
            )
            .where(access_targets_table.c.flat_id == flat_id)
            .order_by(access_requests_table.c.id.desc())
        )
        result = await self._session.execute(stmt)
        return result.tuples().all()

    async def add_slots(
        self,
        access_request_id: AccessRequestId,
        slots: Sequence[tuple[datetime, int]],
    ) -> Sequence[AccessSlot]:
        rows = [
            AccessSlot(
                access_request_id=access_request_id,
                starts_at=starts_at,
                capacity=capacity,
            )
            for starts_at, capacity in slots
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return rows

    async def add_targets(
        self,
        access_request_id: AccessRequestId,
        flat_ids: Sequence[FlatId],
    ) -> Sequence[AccessTarget]:
        rows = [
            AccessTarget(access_request_id=access_request_id, flat_id=flat_id)
            for flat_id in flat_ids
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return rows

    async def list_slots(
        self,
        access_request_ids: Collection[AccessRequestId],
    ) -> Sequence[AccessSlot]:
        stmt = (
            select(AccessSlot)
            .where(access_slots_table.c.access_request_id.in_(access_request_ids))
            .order_by(access_slots_table.c.starts_at)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_targets(
        self,
        access_request_id: AccessRequestId,
    ) -> Sequence[AccessTarget]:
        stmt = (
            select(AccessTarget)
            .where(access_targets_table.c.access_request_id == access_request_id)
            .order_by(access_targets_table.c.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def target_for_flats(
        self,
        access_request_id: AccessRequestId,
        flat_ids: Collection[FlatId],
    ) -> AccessTarget | None:
        # житель приходит сюда без зависимости о доме, поэтому ячейку ищет
        # его собственная подтвержденная квартира, а не id из тела запроса
        if not flat_ids:
            return None
        stmt = select(AccessTarget).where(
            access_targets_table.c.access_request_id == access_request_id,
            access_targets_table.c.flat_id.in_(flat_ids),
        )
        target: AccessTarget | None = await self._session.scalar(stmt)
        return target

    async def lock_slot(
        self,
        access_request_id: AccessRequestId,
        slot_id: AccessSlotId,
    ) -> AccessSlot | None:
        # вместимость больше единицы, поэтому уникальный индекс ее не удержит:
        # блокировка строки слота выстраивает выборы этого окна в очередь
        stmt = (
            select(AccessSlot)
            .where(
                access_slots_table.c.id == slot_id,
                access_slots_table.c.access_request_id == access_request_id,
            )
            .with_for_update()
        )
        slot: AccessSlot | None = await self._session.scalar(stmt)
        return slot

    async def count_picks(self, slot_id: AccessSlotId) -> int:
        stmt = (
            select(func.count())
            .select_from(access_targets_table)
            .where(access_targets_table.c.slot_id == slot_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def pick(
        self,
        target: AccessTarget,
        slot_id: AccessSlotId,
        at: datetime,
    ) -> None:
        target.slot_id = slot_id
        # ответил житель один раз: смена решения не новый ответ, и счетчик
        # «ответили 9 из 14» от нее не двигается
        if target.responded_at is None:
            target.responded_at = at
        await self._session.flush()

    async def picks_by_slot(
        self,
        access_request_ids: Collection[AccessRequestId],
    ) -> dict[AccessSlotId, int]:
        stmt = (
            select(access_targets_table.c.slot_id, func.count())
            .where(
                access_targets_table.c.access_request_id.in_(access_request_ids),
                access_targets_table.c.slot_id.is_not(None),
            )
            .group_by(access_targets_table.c.slot_id)
        )
        result = await self._session.execute(stmt)
        return {AccessSlotId(slot_id): count for slot_id, count in result.tuples()}

    async def counters(
        self,
        access_request_ids: Collection[AccessRequestId],
    ) -> dict[AccessRequestId, tuple[int, int]]:
        stmt = (
            select(
                access_targets_table.c.access_request_id,
                func.count(access_targets_table.c.responded_at),
                func.count(),
            )
            .where(
                access_targets_table.c.access_request_id.in_(access_request_ids),
            )
            .group_by(access_targets_table.c.access_request_id)
        )
        result = await self._session.execute(stmt)
        return {
            AccessRequestId(request_id): (responded, total)
            for request_id, responded, total in result.tuples()
        }
