from collections.abc import Collection, Sequence
from datetime import datetime

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import ResidentRole, ResidentStatus
from zheka.core.errors import EntityNotFound
from zheka.core.ids import FlatId, HouseId, OrgId, ResidentId, UserId
from zheka.infra.database.models import Resident, VerificationRevocation
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.repos.scopes import scoped_to_org
from zheka.infra.database.tables.houses import flats_table
from zheka.infra.database.tables.residents import (
    residents_table,
    verification_revocations_table,
)
from zheka.infra.database.tables.users import users_table

VERIFIED_RESIDENT = and_(
    residents_table.c.verified_at.is_not(None),
    residents_table.c.status != ResidentStatus.BLOCKED,
)


class ResidentsRepo(BaseAlchemyRepo):
    async def list_for_user(self, user_id: UserId) -> Sequence[Resident]:
        stmt = (
            select(Resident)
            .where(residents_table.c.user_id == user_id)
            .order_by(residents_table.c.created_at)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get(self, resident_id: ResidentId) -> Resident | None:
        stmt = select(Resident).where(residents_table.c.id == resident_id)
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
            VERIFIED_RESIDENT,
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
        flat_number: str | None,
        role: ResidentRole,
    ) -> tuple[Resident, bool]:
        is_owner = role is ResidentRole.OWNER
        stmt = (
            pg_insert(Resident)
            .values(
                user_id=user_id,
                house_id=house_id,
                flat_id=flat_id,
                flat_number=flat_number,
                role=role,
                can_see_charges=is_owner,
                can_vote=is_owner,
            )
            .on_conflict_do_nothing(
                index_elements=[residents_table.c.user_id, residents_table.c.house_id],
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
        if flat_id is not None:
            existing.flat_id = flat_id
            existing.flat_number = None
        elif flat_number is not None:
            existing.flat_id = None
            existing.flat_number = flat_number
        existing.role = role
        existing.can_see_charges = is_owner
        existing.can_vote = is_owner
        await self._session.flush()
        return existing, False

    async def delete(self, resident: Resident) -> None:
        await self._session.delete(resident)
        await self._session.flush()

    async def get_for_org(
        self,
        resident_id: ResidentId,
        org_id: OrgId,
    ) -> Resident | None:
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
                users_table.c.name.icontains(query, autoescape=True),
            )
            by_flat = select(flats_table.c.id).where(
                flats_table.c.house_id == house_id,
                flats_table.c.number.istartswith(query, autoescape=True),
            )
            stmt = stmt.where(
                or_(
                    residents_table.c.user_id.in_(by_name),
                    residents_table.c.flat_id.in_(by_flat),
                ),
            )

        stmt = stmt.order_by(residents_table.c.created_at)
        return await self._page(stmt, limit, offset)

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
        if resident.flat_id is not None:
            stmt = (
                pg_insert(VerificationRevocation)
                .values(user_id=resident.user_id, flat_id=resident.flat_id)
                .on_conflict_do_nothing()
            )
            await self._session.execute(stmt)
        resident.verified_at = None
        resident.verified_by = None
        resident.is_chairman = False
        await self._session.flush()

    async def set_verified(
        self,
        resident: Resident,
        flat_id: FlatId,
        at: datetime,
        by: UserId | None,
    ) -> None:
        resident.flat_id = flat_id
        resident.flat_number = None
        resident.verified_at = at
        resident.verified_by = by
        await self._session.flush()

    async def active_residents(
        self,
        house_ids: Collection[HouseId],
    ) -> Sequence[Resident]:
        if not house_ids:
            return []
        stmt = (
            select(Resident)
            .where(
                residents_table.c.house_id.in_(house_ids),
                residents_table.c.status == ResidentStatus.ACTIVE,
            )
            .distinct(residents_table.c.user_id)
            .order_by(residents_table.c.user_id, residents_table.c.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_houses_and_users(
        self,
        house_ids: Collection[HouseId],
        user_ids: Collection[UserId],
    ) -> Sequence[Resident]:
        if not house_ids or not user_ids:
            return []
        stmt = select(Resident).where(
            residents_table.c.house_id.in_(house_ids),
            residents_table.c.user_id.in_(user_ids),
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_verified_for_flats(
        self,
        flat_ids: Collection[FlatId],
    ) -> Sequence[Resident]:
        if not flat_ids:
            return []
        stmt = select(Resident).where(
            residents_table.c.flat_id.in_(flat_ids),
            VERIFIED_RESIDENT,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def is_revoked(self, user_id: UserId, flat_id: FlatId) -> bool:
        stmt = select(
            exists().where(
                verification_revocations_table.c.user_id == user_id,
                verification_revocations_table.c.flat_id == flat_id,
            ),
        )
        return bool(await self._session.scalar(stmt))

    async def active_residents_in(
        self,
        house_id: HouseId,
        entrances: Collection[int],
        flat_ids: Collection[FlatId],
    ) -> Sequence[Resident]:
        stmt = (
            select(Resident)
            .join(flats_table, flats_table.c.id == residents_table.c.flat_id)
            .where(
                residents_table.c.house_id == house_id,
                residents_table.c.status == ResidentStatus.ACTIVE,
                or_(
                    flats_table.c.entrance.in_(entrances),
                    and_(
                        flats_table.c.id.in_(flat_ids),
                        residents_table.c.verified_at.is_not(None),
                    ),
                ),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
