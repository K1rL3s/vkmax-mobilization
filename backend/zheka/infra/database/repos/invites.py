from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import OrgRole
from zheka.core.ids import OrgId, UserId
from zheka.infra.database.models import OrgInvite
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.invites import org_invites_table


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
        # None означает, что код уже занят: вызывающий берет следующий. Через
        # ON CONFLICT, а не через исключение, - иначе транзакция вызывающего
        # уйдет в откат целиком
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
        # аннотация обязательна: OrgInvite отображен императивно, и scalar()
        # для такой сущности возвращает Any
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
        # проверка и инкремент одним UPDATE: два параллельных запроса на
        # последнюю активацию иначе прошли бы лимит оба
        stmt = (
            update(OrgInvite)
            .where(
                org_invites_table.c.code == code,
                org_invites_table.c.revoked_at.is_(None),
                org_invites_table.c.expires_at > func.now(),
                org_invites_table.c.activations_used
                < org_invites_table.c.max_activations,
            )
            .values(activations_used=org_invites_table.c.activations_used + 1)
            .returning(OrgInvite)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke(self, invite: OrgInvite, at: datetime) -> None:
        invite.revoked_at = at
        await self._session.flush()
