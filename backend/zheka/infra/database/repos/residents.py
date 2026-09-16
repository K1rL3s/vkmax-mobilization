from collections.abc import Sequence

from sqlalchemy import select

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
