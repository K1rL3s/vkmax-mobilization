from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, select, update

from zheka.core.enums import AnnouncementChannel
from zheka.core.ids import AnnouncementId, HouseId, OrgId, UserId
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
        *,
        urgent: bool,
        delivered_direct: int | None,
        delivered_chat: int | None,
    ) -> Announcement:
        announcement = Announcement(
            org_id=org_id,
            house_ids=list(house_ids),
            text=text,
            channels=[channel.value for channel in channels],
            created_by=created_by,
            recipients_count=recipients_count,
            urgent=urgent,
            delivered_direct=delivered_direct,
            delivered_chat=delivered_chat,
        )
        self._session.add(announcement)
        await self._session.flush()
        return announcement

    async def list_for_house(
        self,
        house_id: HouseId,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Announcement], int]:
        stmt = select(Announcement).where(
            announcements_table.c.house_ids.contains([house_id]),
        )
        return await self._newest_first(stmt, limit, offset)

    async def list_for_house_since(
        self,
        house_id: HouseId,
        since: datetime,
    ) -> Sequence[Announcement]:
        stmt = (
            select(Announcement)
            .where(
                announcements_table.c.house_ids.contains([house_id]),
                announcements_table.c.created_at >= since,
            )
            .order_by(
                announcements_table.c.created_at.desc(),
                announcements_table.c.id.desc(),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_org(
        self,
        org_id: OrgId,
        house_id: HouseId | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Announcement], int]:
        stmt = select(Announcement).where(announcements_table.c.org_id == org_id)
        if house_id is not None:
            stmt = stmt.where(announcements_table.c.house_ids.contains([house_id]))
        return await self._newest_first(stmt, limit, offset)

    async def _newest_first(
        self,
        stmt: Select[tuple[Announcement]],
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Announcement], int]:
        stmt = stmt.order_by(
            announcements_table.c.created_at.desc(),
            announcements_table.c.id.desc(),
        )
        return await self._page(stmt, limit, offset)

    async def set_delivered(
        self,
        announcement_id: AnnouncementId,
        *,
        direct: int | None = None,
        chat: int | None = None,
    ) -> None:
        values = {"delivered_direct": direct, "delivered_chat": chat}
        stmt = (
            update(announcements_table)
            .where(announcements_table.c.id == announcement_id)
            .values({key: value for key, value in values.items() if value is not None})
        )
        await self._session.execute(stmt)
