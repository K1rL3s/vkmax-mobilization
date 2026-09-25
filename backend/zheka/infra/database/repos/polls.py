from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import PollStatus
from zheka.core.ids import (
    FlatId,
    HouseId,
    OrgId,
    PollId,
    PollOptionId,
    ResidentId,
    UserId,
)
from zheka.infra.database.models import Poll, PollOption, PollVote
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.polls import (
    poll_options_table,
    poll_votes_table,
    polls_table,
)


class PollsRepo(BaseAlchemyRepo):
    async def create(
        self,
        house_id: HouseId,
        org_id: OrgId | None,
        created_by_user_id: UserId,
        created_by_role: str,
        title: str,
        description: str | None,
        is_multiple: bool,
        starts_at: datetime,
        ends_at: datetime,
        options: Sequence[str],
    ) -> Poll:
        poll = Poll(
            house_id=house_id,
            org_id=org_id,
            created_by_user_id=created_by_user_id,
            created_by_role=created_by_role,
            title=title,
            description=description,
            is_multiple=is_multiple,
            starts_at=starts_at,
            ends_at=ends_at,
            status=PollStatus.ACTIVE,
        )
        self._session.add(poll)
        await self._session.flush()
        for position, text in enumerate(options):
            self._session.add(PollOption(poll_id=poll.id, text=text, position=position))
        await self._session.flush()
        return poll

    async def get(self, poll_id: PollId) -> Poll | None:
        stmt = select(Poll).where(polls_table.c.id == poll_id)
        poll: Poll | None = await self._session.scalar(stmt)
        return poll

    async def list_options(self, poll_id: PollId) -> Sequence[PollOption]:
        stmt = (
            select(PollOption)
            .where(poll_options_table.c.poll_id == poll_id)
            .order_by(poll_options_table.c.position)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_house(self, house_id: HouseId) -> Sequence[Poll]:
        stmt = select(Poll).where(polls_table.c.house_id == house_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_org(
        self,
        org_id: OrgId,
        house_id: HouseId | None,
    ) -> Sequence[Poll]:
        stmt = select(Poll).where(polls_table.c.org_id == org_id)
        if house_id is not None:
            stmt = stmt.where(polls_table.c.house_id == house_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_vote(self, poll_id: PollId, user_id: UserId) -> Sequence[PollVote]:
        stmt = select(PollVote).where(
            poll_votes_table.c.poll_id == poll_id,
            poll_votes_table.c.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_votes(self, poll_id: PollId) -> Sequence[PollVote]:
        stmt = select(PollVote).where(poll_votes_table.c.poll_id == poll_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add_vote(
        self,
        poll_id: PollId,
        option_ids: Sequence[PollOptionId],
        user_id: UserId,
        resident_id: ResidentId,
        flat_id: FlatId | None,
        *,
        counted_by_area: bool,
    ) -> Sequence[PollVote]:
        stmt = (
            pg_insert(PollVote)
            .values(
                [
                    {
                        "poll_id": poll_id,
                        "option_id": option_id,
                        "user_id": user_id,
                        "resident_id": resident_id,
                        "flat_id": flat_id,
                        "counted_by_area": counted_by_area,
                    }
                    for option_id in option_ids
                ],
            )
            .on_conflict_do_nothing(
                index_elements=[
                    poll_votes_table.c.poll_id,
                    poll_votes_table.c.user_id,
                    poll_votes_table.c.option_id,
                ],
            )
            .returning(PollVote)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def voted_flat_ids(self, poll_id: PollId) -> Sequence[FlatId]:
        stmt = (
            select(poll_votes_table.c.flat_id)
            .where(
                poll_votes_table.c.poll_id == poll_id,
                poll_votes_table.c.flat_id.is_not(None),
                poll_votes_table.c.counted_by_area.is_(True),
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def close(self, poll: Poll) -> None:
        poll.status = PollStatus.CLOSED
        await self._session.flush()

    async def list_to_remind(self, now: datetime, until: datetime) -> Sequence[Poll]:
        stmt = select(Poll).where(
            polls_table.c.status == PollStatus.ACTIVE,
            polls_table.c.reminder_sent_at.is_(None),
            polls_table.c.ends_at > now,
            polls_table.c.ends_at <= until,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def mark_reminded(self, poll: Poll, at: datetime) -> None:
        poll.reminder_sent_at = at
        await self._session.flush()

    async def close_expired(self, now: datetime) -> int:
        stmt = (
            update(polls_table)
            .where(
                polls_table.c.status == PollStatus.ACTIVE,
                polls_table.c.ends_at <= now,
            )
            .values(status=PollStatus.CLOSED)
            .returning(polls_table.c.id)
        )
        result = await self._session.execute(stmt)
        return len(result.scalars().all())

    async def voter_ids(self, poll_id: PollId) -> Sequence[UserId]:
        stmt = (
            select(poll_votes_table.c.user_id)
            .where(poll_votes_table.c.poll_id == poll_id)
            .distinct()
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
