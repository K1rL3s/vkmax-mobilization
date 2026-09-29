from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    ColumnElement,
    DateTime,
    Select,
    String,
    and_,
    cast,
    column,
    or_,
    select,
    update,
    values,
)
from sqlalchemy.orm.attributes import set_committed_value

from zheka.core.enums import AnnouncementChannel, NoticeStatus, RequestCategory
from zheka.core.ids import AnnouncementId, FlatId, HouseId, OrgId, PollId, UserId
from zheka.infra.database.models import Announcement, NoticeDelivery
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.announcements import (
    announcements_table,
    notice_deliveries_table,
)

WHOLE_HOUSE = and_(
    announcements_table.c.entrances.is_(None),
    announcements_table.c.flat_ids.is_(None),
)


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
        entrances: Sequence[int] | None,
        flat_ids: Sequence[FlatId] | None,
        poll_id: PollId | None,
        works_category: RequestCategory | None,
        works_from: datetime | None,
        works_until: datetime | None,
        documents: Sequence[Mapping[str, str]],
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
            entrances=None if entrances is None else list(entrances),
            flat_ids=None if flat_ids is None else list(flat_ids),
            poll_id=poll_id,
            works_category=works_category,
            works_from=works_from,
            works_until=works_until,
            documents=[dict(document) for document in documents],
        )
        self._session.add(announcement)
        await self._session.flush()
        return announcement

    async def list_for_house(
        self,
        house_id: HouseId,
        entrance: int | None,
        flat_id: FlatId | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Announcement], int]:
        stmt = select(Announcement).where(*_seen_in(house_id, entrance, flat_id))
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
                WHOLE_HOUSE,
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
        poll_id: PollId | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Announcement], int]:
        stmt = select(Announcement).where(announcements_table.c.org_id == org_id)
        if house_id is not None:
            stmt = stmt.where(announcements_table.c.house_ids.contains([house_id]))
        if poll_id is not None:
            stmt = stmt.where(announcements_table.c.poll_id == poll_id)
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

    async def get_for_org(
        self,
        announcement_id: AnnouncementId,
        org_id: OrgId,
    ) -> Announcement | None:
        stmt = select(Announcement).where(
            announcements_table.c.id == announcement_id,
            announcements_table.c.org_id == org_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_deliveries(self, deliveries: Sequence[NoticeDelivery]) -> None:
        self._session.add_all(deliveries)
        await self._session.flush()

    async def set_deliveries(
        self,
        announcement_id: AnnouncementId,
        results: Mapping[UserId, tuple[NoticeStatus, datetime]],
    ) -> None:
        rows = values(
            column("user_id", BigInteger),
            column("status", String),
            column("at", DateTime(timezone=True)),
            name="results",
        ).data([(user_id, *result) for user_id, result in results.items()])
        stmt = (
            update(notice_deliveries_table)
            .where(
                notice_deliveries_table.c.announcement_id == announcement_id,
                notice_deliveries_table.c.user_id == rows.c.user_id,
            )
            .values(
                status=cast(rows.c.status, notice_deliveries_table.c.status.type),
                at=rows.c.at,
            )
        )
        await self._session.execute(stmt)

    async def deliveries(
        self,
        announcement_id: AnnouncementId,
        house_id: HouseId,
    ) -> Sequence[NoticeDelivery]:
        stmt = select(NoticeDelivery).where(
            notice_deliveries_table.c.announcement_id == announcement_id,
            notice_deliveries_table.c.house_id == house_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def active_works(
        self,
        house_id: HouseId,
        entrance: int | None,
        flat_id: FlatId | None,
        category: RequestCategory,
        now: datetime,
    ) -> Announcement | None:
        stmt = (
            select(Announcement)
            .where(
                *_seen_in(house_id, entrance, flat_id),
                announcements_table.c.works_category == category,
                announcements_table.c.works_from <= now,
                announcements_table.c.works_until > now,
            )
            .order_by(announcements_table.c.works_until.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def finish_works(self, announcement: Announcement, now: datetime) -> bool:
        stmt = (
            update(announcements_table)
            .where(
                announcements_table.c.id == announcement.id,
                announcements_table.c.works_from <= now,
                announcements_table.c.works_until > now,
            )
            .values(works_until=now)
            .returning(announcements_table.c.id)
        )
        result = await self._session.execute(stmt)
        if result.scalar_one_or_none() is None:
            return False
        set_committed_value(announcement, "works_until", now)
        return True

    async def addressees(self, announcement_id: AnnouncementId) -> Sequence[UserId]:
        stmt = select(notice_deliveries_table.c.user_id).where(
            notice_deliveries_table.c.announcement_id == announcement_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


def _seen_in(
    house_id: HouseId,
    entrance: int | None,
    flat_id: FlatId | None,
) -> tuple[ColumnElement[bool], ...]:
    scopes = [WHOLE_HOUSE]
    if entrance is not None:
        scopes.append(announcements_table.c.entrances.contains([entrance]))
    if flat_id is not None:
        scopes.append(announcements_table.c.flat_ids.contains([flat_id]))
    return announcements_table.c.house_ids.contains([house_id]), or_(*scopes)
