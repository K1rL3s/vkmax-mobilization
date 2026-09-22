from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Table, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import OrgRole
from zheka.core.ids import FlatId, OrgId, UserId
from zheka.infra.database.models import FlatInvite, OrgInvite
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.invites import flat_invites_table, org_invites_table


class InvitesRepo(BaseAlchemyRepo):
    async def create(
        self,
        code: str,
        org_id: OrgId,
        role: OrgRole,
        expires_at: datetime,
        max_activations: int,
        created_by: UserId,
    ) -> OrgInvite | None:
        stmt = (
            pg_insert(OrgInvite)
            .values(
                code=code,
                org_id=org_id,
                role=role,
                expires_at=expires_at,
                max_activations=max_activations,
                created_by=created_by,
            )
            .on_conflict_do_nothing(index_elements=[org_invites_table.c.code])
            .returning(OrgInvite)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get(self, code: str) -> OrgInvite | None:
        stmt = select(OrgInvite).where(org_invites_table.c.code == code)
        invite: OrgInvite | None = await self._session.scalar(stmt)
        return invite

    async def list_for_org(self, org_id: OrgId) -> Sequence[OrgInvite]:
        stmt = (
            select(OrgInvite)
            .where(org_invites_table.c.org_id == org_id)
            .order_by(org_invites_table.c.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def consume(self, code: str) -> OrgInvite | None:
        return await self._consume(OrgInvite, org_invites_table, code)

    async def revoke(self, invite: OrgInvite, at: datetime) -> None:
        invite.revoked_at = at
        await self._session.flush()

    async def create_flat(
        self,
        code: str,
        flat_id: FlatId,
        expires_at: datetime,
        max_activations: int,
        created_by: UserId,
    ) -> FlatInvite | None:
        stmt = (
            pg_insert(FlatInvite)
            .values(
                code=code,
                flat_id=flat_id,
                expires_at=expires_at,
                max_activations=max_activations,
                created_by=created_by,
            )
            .on_conflict_do_nothing(index_elements=[flat_invites_table.c.code])
            .returning(FlatInvite)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_flat(self, code: str) -> FlatInvite | None:
        stmt = select(FlatInvite).where(flat_invites_table.c.code == code)
        invite: FlatInvite | None = await self._session.scalar(stmt)
        return invite

    async def list_for_flat(self, flat_id: FlatId) -> Sequence[FlatInvite]:
        stmt = (
            select(FlatInvite)
            .where(flat_invites_table.c.flat_id == flat_id)
            .order_by(flat_invites_table.c.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def consume_flat(self, code: str) -> FlatInvite | None:
        return await self._consume(FlatInvite, flat_invites_table, code)

    async def revoke_flat(self, invite: FlatInvite, at: datetime) -> None:
        invite.revoked_at = at
        await self._session.flush()

    async def _consume[InviteT](
        self,
        model: type[InviteT],
        table: Table,
        code: str,
    ) -> InviteT | None:
        stmt = (
            update(model)
            .where(
                table.c.code == code,
                table.c.revoked_at.is_(None),
                table.c.expires_at > func.now(),
                table.c.activations_used < table.c.max_activations,
            )
            .values(activations_used=table.c.activations_used + 1)
            .returning(model)
        )
        result = await self._session.execute(stmt)
        invite: InviteT | None = result.scalar_one_or_none()
        return invite
