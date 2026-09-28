from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.ids import HouseId, UserId
from zheka.infra.database.models import ChairmanHandover
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.residents import chairman_handovers_table


class ChairmanRepo(BaseAlchemyRepo):
    async def create(
        self,
        code: str,
        house_id: HouseId,
        created_by: UserId,
        expires_at: datetime,
    ) -> ChairmanHandover | None:
        stmt = (
            pg_insert(ChairmanHandover)
            .values(
                code=code,
                house_id=house_id,
                created_by=created_by,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(index_elements=[chairman_handovers_table.c.code])
            .returning(ChairmanHandover)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get(self, code: str) -> ChairmanHandover | None:
        stmt = select(ChairmanHandover).where(
            chairman_handovers_table.c.code == code,
        )
        handover: ChairmanHandover | None = await self._session.scalar(stmt)
        return handover

    async def lock(self, code: str) -> ChairmanHandover | None:
        stmt = (
            select(ChairmanHandover)
            .where(chairman_handovers_table.c.code == code)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        handover: ChairmanHandover | None = await self._session.scalar(stmt)
        return handover

    async def get_open(
        self,
        house_id: HouseId,
        now: datetime,
    ) -> ChairmanHandover | None:
        stmt = select(ChairmanHandover).where(
            chairman_handovers_table.c.house_id == house_id,
            chairman_handovers_table.c.decided_at.is_(None),
            chairman_handovers_table.c.revoked_at.is_(None),
            chairman_handovers_table.c.expires_at > now,
        )
        handover: ChairmanHandover | None = await self._session.scalar(stmt)
        return handover

    async def close_open(self, house_id: HouseId, at: datetime) -> None:
        stmt = (
            update(ChairmanHandover)
            .where(
                chairman_handovers_table.c.house_id == house_id,
                chairman_handovers_table.c.decided_at.is_(None),
                chairman_handovers_table.c.revoked_at.is_(None),
            )
            .values(revoked_at=at)
        )
        await self._session.execute(stmt)

    async def decide(
        self,
        handover: ChairmanHandover,
        at: datetime,
        accepted_by: UserId | None,
    ) -> None:
        handover.decided_at = at
        handover.accepted_by = accepted_by
        await self._session.flush()
