from collections.abc import Collection, Sequence

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import ResidentRole, ResidentStatus
from zheka.core.errors import EntityNotFound
from zheka.core.ids import FlatId, HouseId, OrgId, ResidentId, UserId
from zheka.infra.database.models import Resident
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.repos.scopes import scoped_to_org
from zheka.infra.database.tables.houses import flats_table
from zheka.infra.database.tables.residents import residents_table
from zheka.infra.database.tables.users import users_table


class ResidentsRepo(BaseAlchemyRepo):
    async def list_for_user(self, user_id: UserId) -> Sequence[Resident]:
        stmt = select(Resident).where(residents_table.c.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get(self, resident_id: ResidentId) -> Resident | None:
        stmt = select(Resident).where(residents_table.c.id == resident_id)
        # аннотация обязательна: Resident отображен императивно, и scalar()
        # для такой сущности возвращает Any
        resident: Resident | None = await self._session.scalar(stmt)
        return resident

    async def get_for_house(
        self,
        user_id: UserId,
        house_id: HouseId,
    ) -> Resident | None:
        stmt = select(Resident).where(
            residents_table.c.user_id == user_id,
            residents_table.c.house_id == house_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_house(self, house_id: HouseId) -> Sequence[Resident]:
        stmt = select(Resident).where(residents_table.c.house_id == house_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_verified_for_house(self, house_id: HouseId) -> Sequence[Resident]:
        stmt = select(Resident).where(
            residents_table.c.house_id == house_id,
            residents_table.c.verified_at.is_not(None),
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_flat(self, flat_id: FlatId) -> Sequence[Resident]:
        stmt = select(Resident).where(residents_table.c.flat_id == flat_id)
        result = await self._session.execute(stmt)
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

    async def get_for_org(
        self,
        resident_id: ResidentId,
        org_id: OrgId,
    ) -> Resident | None:
        # resident_id приходит из пути, поэтому запрос сужается до домов
        # организации: чужой житель отвечает 404, а не 403
        stmt = scoped_to_org(
            select(Resident).where(residents_table.c.id == resident_id),
            residents_table.c.house_id,
            org_id,
        )
        resident: Resident | None = await self._session.scalar(stmt)
        return resident

    async def search_for_house(
        self,
        house_id: HouseId,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Resident], int]:
        stmt = select(Resident).where(residents_table.c.house_id == house_id)
        if query is not None:
            by_name = select(users_table.c.id).where(
                users_table.c.name.ilike(f"%{query}%"),
            )
            by_flat = select(flats_table.c.id).where(
                flats_table.c.house_id == house_id,
                flats_table.c.number.ilike(f"{query}%"),
            )
            stmt = stmt.where(
                or_(
                    residents_table.c.user_id.in_(by_name),
                    residents_table.c.flat_id.in_(by_flat),
                ),
            )

        total = await self._count(stmt)
        page_stmt = (
            stmt.order_by(residents_table.c.created_at).limit(limit).offset(offset)
        )
        result = await self._session.execute(page_stmt)
        return result.scalars().all(), total

    async def count_by_house(
        self,
        house_ids: Collection[HouseId],
    ) -> dict[HouseId, int]:
        if not house_ids:
            return {}
        stmt = (
            select(residents_table.c.house_id, func.count())
            .where(residents_table.c.house_id.in_(house_ids))
            .group_by(residents_table.c.house_id)
        )
        result = await self._session.execute(stmt)
        return {HouseId(house_id): count for house_id, count in result.tuples().all()}

    async def count_verified(self, house_id: HouseId) -> int:
        stmt = (
            select(func.count())
            .select_from(residents_table)
            .where(
                residents_table.c.house_id == house_id,
                residents_table.c.verified_at.is_not(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_chairman(self, house_id: HouseId) -> Resident | None:
        stmt = select(Resident).where(
            residents_table.c.house_id == house_id,
            residents_table.c.is_chairman.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_chairman(self, house_id: HouseId) -> None:
        stmt = (
            update(Resident)
            .where(
                residents_table.c.house_id == house_id,
                residents_table.c.is_chairman.is_(True),
            )
            .values(is_chairman=False)
        )
        await self._session.execute(stmt)

    async def set_chairman(self, resident: Resident, value: bool) -> None:
        resident.is_chairman = value
        await self._session.flush()

    async def set_status(
        self,
        resident: Resident,
        status: ResidentStatus,
        reason: str | None,
    ) -> None:
        resident.status = status
        resident.block_reason = reason
        await self._session.flush()

    async def revoke_verification(self, resident: Resident) -> None:
        resident.verified_at = None
        resident.verified_by = None
        resident.is_chairman = False
        await self._session.flush()
