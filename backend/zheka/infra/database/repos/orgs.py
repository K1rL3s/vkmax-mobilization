from collections.abc import Collection, Sequence

from sqlalchemy import select

from zheka.core.ids import OrgId, UserId
from zheka.infra.database.models import OrgMember, OrgSettings, Organization
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.organizations import (
    org_members_table,
    organizations_table,
)


class OrgsRepo(BaseAlchemyRepo):
    async def get(self, org_id: OrgId) -> Organization | None:
        return await self._session.get(Organization, org_id)

    async def get_by_inn(self, inn: str) -> Organization | None:
        result = await self._session.execute(
            select(Organization).where(organizations_table.c.inn == inn),
        )
        return result.scalar_one_or_none()

    async def get_by_license(self, license_no: str) -> Organization | None:
        result = await self._session.execute(
            select(Organization).where(organizations_table.c.license_no == license_no),
        )
        return result.scalar_one_or_none()

    async def list_members(self, org_id: OrgId) -> Sequence[OrgMember]:
        result = await self._session.execute(
            select(OrgMember).where(org_members_table.c.org_id == org_id),
        )
        return result.scalars().all()

    async def get_member(self, org_id: OrgId, user_id: UserId) -> OrgMember | None:
        result = await self._session.execute(
            select(OrgMember).where(
                org_members_table.c.org_id == org_id,
                org_members_table.c.user_id == user_id,
            ),
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: UserId) -> Sequence[OrgMember]:
        result = await self._session.execute(
            select(OrgMember).where(org_members_table.c.user_id == user_id),
        )
        return result.scalars().all()

    async def get_settings(self, org_id: OrgId) -> OrgSettings | None:
        return await self._session.get(OrgSettings, org_id)

    async def list_by_ids(self, org_ids: Collection[OrgId]) -> Sequence[Organization]:
        if not org_ids:
            return []
        stmt = select(Organization).where(organizations_table.c.id.in_(org_ids))
        result = await self._session.execute(stmt)
        return result.scalars().all()
