from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import ResidentRole
from zheka.core.errors import EntityNotFound
from zheka.core.ids import FlatId, HouseId, ResidentId, UserId
from zheka.infra.database.models import Resident
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.residents import residents_table


class ResidentsRepo(BaseAlchemyRepo):
    async def list_for_user(self, user_id: UserId) -> Sequence[Resident]:
        result = await self._session.execute(
            select(Resident).where(residents_table.c.user_id == user_id),
        )
        return result.scalars().all()

    async def get(self, resident_id: ResidentId) -> Resident | None:
        return await self._session.get(Resident, resident_id)

    async def get_for_house(
        self,
        user_id: UserId,
        house_id: HouseId,
    ) -> Resident | None:
        result = await self._session.execute(
            select(Resident).where(
                residents_table.c.user_id == user_id,
                residents_table.c.house_id == house_id,
            ),
        )
        return result.scalar_one_or_none()

    async def list_for_house(self, house_id: HouseId) -> Sequence[Resident]:
        result = await self._session.execute(
            select(Resident).where(residents_table.c.house_id == house_id),
        )
        return result.scalars().all()

    async def list_verified_for_house(self, house_id: HouseId) -> Sequence[Resident]:
        result = await self._session.execute(
            select(Resident).where(
                residents_table.c.house_id == house_id,
                residents_table.c.verified_at.is_not(None),
            ),
        )
        return result.scalars().all()

    async def list_for_flat(self, flat_id: FlatId) -> Sequence[Resident]:
        result = await self._session.execute(
            select(Resident).where(residents_table.c.flat_id == flat_id),
        )
        return result.scalars().all()

    async def add_or_get(
        self,
        user_id: UserId,
        house_id: HouseId,
        flat_id: FlatId | None,
        role: ResidentRole,
    ) -> tuple[Resident, bool]:
        # идемпотентность привязки держит уникальный индекс (user_id, house_id),
        # а не чтение перед записью: два параллельных запроса прошли бы его оба.
        # Второй элемент кортежа - завели ли жителя этим вызовом
        is_owner = role is ResidentRole.OWNER
        stmt = (
            pg_insert(Resident)
            .values(
                user_id=user_id,
                house_id=house_id,
                flat_id=flat_id,
                role=role,
                # арендатор не видит начислений и не голосует
                can_see_charges=is_owner,
                can_vote=is_owner,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    residents_table.c.user_id,
                    residents_table.c.house_id,
                ],
            )
            .returning(Resident)
        )
        result = await self._session.execute(stmt)
        created = result.scalar_one_or_none()
        if created is not None:
            return created, True

        existing = await self.get_for_house(user_id, house_id)
        if existing is None:
            raise EntityNotFound("Житель не найден")
        # квартиру получает житель, у которого ее еще нет: диплинк из домового
        # чата привязывает к дому, не зная квартиры, и она выбирается потом
        if existing.flat_id is None and flat_id is not None:
            existing.flat_id = flat_id
        # повторная привязка не молчит о роли: иначе тот, кто однажды вошел
        # арендатором, навсегда остался бы без начислений и голоса
        existing.role = role
        existing.can_see_charges = is_owner
        existing.can_vote = is_owner
        await self._session.flush()
        return existing, False

    async def delete(self, resident: Resident) -> None:
        await self._session.delete(resident)
        # запись события идет по savepoint поверх этой же сессии, поэтому
        # удаление доводится до базы до нее, а не внутри нее
        await self._session.flush()
