from collections.abc import Collection, Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import OrgRole
from zheka.core.errors import ORG_NOT_FOUND, EntityNotFound
from zheka.core.ids import OrgId, UserId
from zheka.infra.database.models import OrgMember, OrgSettings, Organization
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.organizations import (
    org_members_table,
    org_settings_table,
    organizations_table,
)


class OrgsRepo(BaseAlchemyRepo):
    async def get(self, org_id: OrgId) -> Organization | None:
        stmt = select(Organization).where(organizations_table.c.id == org_id)
        org: Organization | None = await self._session.scalar(stmt)
        return org

    async def get_by_inn(self, inn: str) -> Organization | None:
        stmt = select(Organization).where(organizations_table.c.inn == inn)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_license(self, license_no: str) -> Organization | None:
        stmt = select(Organization).where(
            organizations_table.c.license_no == license_no,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_members(self, org_id: OrgId) -> Sequence[OrgMember]:
        stmt = select(OrgMember).where(org_members_table.c.org_id == org_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_member(self, org_id: OrgId, user_id: UserId) -> OrgMember | None:
        stmt = select(OrgMember).where(
            org_members_table.c.org_id == org_id,
            org_members_table.c.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: UserId) -> Sequence[OrgMember]:
        stmt = select(OrgMember).where(org_members_table.c.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_settings(self, org_id: OrgId) -> OrgSettings | None:
        stmt = select(OrgSettings).where(org_settings_table.c.org_id == org_id)
        settings: OrgSettings | None = await self._session.scalar(stmt)
        return settings

    async def list_by_ids(self, org_ids: Collection[OrgId]) -> Sequence[Organization]:
        if not org_ids:
            return []
        stmt = select(Organization).where(organizations_table.c.id.in_(org_ids))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_members(self, org_id: OrgId) -> int:
        stmt = (
            select(func.count())
            .select_from(org_members_table)
            .where(org_members_table.c.org_id == org_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def add_member(
        self,
        org_id: OrgId,
        user_id: UserId,
        role: OrgRole,
    ) -> OrgMember:
        member = OrgMember(org_id=org_id, user_id=user_id, role=role)
        self._session.add(member)
        await self._session.flush()
        return member

    async def set_member_role(self, member: OrgMember, role: OrgRole) -> None:
        member.role = role
        await self._session.flush()

    async def remove_member(self, member: OrgMember) -> None:
        await self._session.delete(member)
        await self._session.flush()

    async def add_settings(self, org_id: OrgId) -> OrgSettings:
        settings = OrgSettings(org_id=org_id)
        self._session.add(settings)
        await self._session.flush()
        return settings

    async def add_member_or_get(
        self,
        org_id: OrgId,
        user_id: UserId,
        role: OrgRole,
    ) -> OrgMember:
        stmt = (
            pg_insert(OrgMember)
            .values(org_id=org_id, user_id=user_id, role=role)
            .on_conflict_do_nothing(
                index_elements=[
                    org_members_table.c.org_id,
                    org_members_table.c.user_id,
                ],
            )
            .returning(OrgMember)
        )
        result = await self._session.execute(stmt)
        created = result.scalar_one_or_none()
        if created is not None:
            return created
        member = await self.get_member(org_id, user_id)
        if member is None:
            raise EntityNotFound("Сотрудник не найден")
        return member

    async def get_existing(self, org_id: OrgId) -> Organization:
        org = await self.get(org_id)
        if org is None:
            raise EntityNotFound(ORG_NOT_FOUND)
        return org
