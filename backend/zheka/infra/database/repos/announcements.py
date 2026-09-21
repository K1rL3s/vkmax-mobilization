from collections.abc import Sequence

from sqlalchemy import Select, select

from zheka.core.enums import AnnouncementChannel
from zheka.core.ids import HouseId, OrgId, UserId
from zheka.infra.database.models import Announcement
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.announcements import announcements_table


class AnnouncementsRepo(BaseAlchemyRepo):
    async def create(
        self,
        org_id: OrgId,
        created_by: UserId,
        house_ids: Sequence[HouseId],
        text: str,
        channels: Sequence[AnnouncementChannel],
        recipients_count: int,
    ) -> Announcement:
        announcement = Announcement(
            org_id=org_id,
            house_ids=list(house_ids),
            text=text,
            channels=[channel.value for channel in channels],
            created_by=created_by,
            recipients_count=recipients_count,
        )
        self._session.add(announcement)
        await self._session.flush()
        return announcement

    async def list_for_house(
        self, house_id: HouseId, limit: int, offset: int
    ) -> tuple[Sequence[Announcement], int]:
        # contains - оператор @>, по нему и работает GIN-индекс на house_ids
        stmt = select(Announcement).where(
            announcements_table.c.house_ids.contains([house_id])
        )
        return await self._page(stmt, limit, offset)

    async def list_for_org(
        self, org_id: OrgId, house_id: HouseId | None, limit: int, offset: int
    ) -> tuple[Sequence[Announcement], int]:
        stmt = select(Announcement).where(announcements_table.c.org_id == org_id)
        if house_id is not None:
            stmt = stmt.where(announcements_table.c.house_ids.contains([house_id]))
        return await self._page(stmt, limit, offset)

    async def _page(
        self, stmt: Select[tuple[Announcement]], limit: int, offset: int
    ) -> tuple[Sequence[Announcement], int]:
        total = await self._count(stmt)
        # id вторым ключом: created_at у двух объявлений одной транзакции
        # совпадает, now() в PostgreSQL общий на транзакцию
        page_stmt = (
            stmt.order_by(
                announcements_table.c.created_at.desc(), announcements_table.c.id.desc()
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(page_stmt)
        return result.scalars().all(), total
