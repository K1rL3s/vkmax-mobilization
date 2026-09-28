from collections.abc import Collection
from datetime import datetime

from sqlalchemy import Integer, cast, func, or_, select

from zheka.base import ZhekaType
from zheka.core.enums import (
    AppointmentStatus,
    HouseState,
    PollStatus,
    RequestCategory,
    RequestStatus,
    VerificationStatus,
)
from zheka.core.ids import AnnouncementId, HouseId, OrgId, PollId
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.repos.polls import COUNTED_FLAT_VOTE
from zheka.infra.database.repos.requests import escalation_active, overdue_at
from zheka.infra.database.repos.scopes import scoped_to_org
from zheka.infra.database.tables.announcements import announcements_table
from zheka.infra.database.tables.houses import flats_table
from zheka.infra.database.tables.polls import poll_votes_table, polls_table
from zheka.infra.database.tables.reception import appointments_table
from zheka.infra.database.tables.requests import requests_table
from zheka.infra.database.tables.residents import (
    flat_verification_requests_table,
    residents_table,
)

_R = requests_table.c


class RequestCounts(ZhekaType):
    open: int = 0
    overdue: int = 0
    escalated: int = 0
    grouped: int = 0
    emergency: int = 0
    period_requests: int = 0
    rating: int | None = None

    @property
    def state(self) -> HouseState:
        if self.emergency:
            return HouseState.EMERGENCY
        if self.escalated:
            return HouseState.ESCALATED
        if self.overdue:
            return HouseState.OVERDUE
        if self.open:
            return HouseState.OPEN
        return HouseState.CALM


class UrgentNotice(ZhekaType):
    announcement_id: AnnouncementId
    text: str
    created_at: datetime


class ActivePoll(ZhekaType):
    poll_id: PollId
    title: str
    ends_at: datetime
    voted_flats: int


class AdminMapRepo(BaseAlchemyRepo):
    async def request_counts(
        self,
        org_id: OrgId,
        category: RequestCategory | None,
        since: datetime,
        now: datetime,
    ) -> dict[HouseId, RequestCounts]:
        is_open = _R.status != RequestStatus.DONE
        is_active = _R.status.not_in((RequestStatus.DONE, RequestStatus.ON_REVIEW))
        in_period = _R.created_at >= since
        stmt = scoped_to_org(
            select(
                _R.house_id,
                func.count().filter(is_open),
                func.count().filter(overdue_at(now)),
                func.count().filter(escalation_active(now, requests_table)),
                func.count().filter(is_open, _R.group_id.is_not(None)),
                func.count().filter(is_active, _R.category == RequestCategory.LEAK),
                func.count().filter(in_period),
                cast(func.round(func.avg(_R.rating).filter(in_period) * 100), Integer),
            )
            .where(or_(is_open, in_period))
            .group_by(_R.house_id),
            _R.house_id,
            org_id,
        )
        if category is not None:
            stmt = stmt.where(_R.category == category)
        result = await self._session.execute(stmt)
        return {
            HouseId(house_id): RequestCounts(
                open=open_,
                overdue=overdue,
                escalated=escalated,
                grouped=grouped,
                emergency=emergency,
                period_requests=period_requests,
                rating=rating,
            )
            for (
                house_id,
                open_,
                overdue,
                escalated,
                grouped,
                emergency,
                period_requests,
                rating,
            ) in result.tuples().all()
        }

    async def urgent_notices(
        self,
        org_id: OrgId,
        since: datetime,
    ) -> dict[HouseId, UrgentNotice]:
        a = announcements_table.c
        stmt = (
            select(a.id, a.text, a.created_at, func.unnest(a.house_ids))
            .where(a.org_id == org_id, a.urgent.is_(True), a.created_at >= since)
            .order_by(a.created_at.desc(), a.id.desc())
        )
        result = await self._session.execute(stmt)
        notices: dict[HouseId, UrgentNotice] = {}
        for announcement_id, text, created_at, house_id in result.tuples().all():
            notices.setdefault(
                HouseId(house_id),
                UrgentNotice(
                    announcement_id=AnnouncementId(announcement_id),
                    text=text,
                    created_at=created_at,
                ),
            )
        return notices

    async def active_polls(
        self,
        org_id: OrgId,
        now: datetime,
    ) -> dict[HouseId, ActivePoll]:
        p = polls_table.c
        voted_flats = (
            select(func.count(poll_votes_table.c.flat_id.distinct()))
            .where(poll_votes_table.c.poll_id == p.id, COUNTED_FLAT_VOTE)
            .scalar_subquery()
        )
        stmt = scoped_to_org(
            select(p.house_id, p.id, p.title, p.ends_at, voted_flats)
            .where(p.status == PollStatus.ACTIVE, p.ends_at > now)
            .order_by(p.ends_at, p.id),
            p.house_id,
            org_id,
        )
        result = await self._session.execute(stmt)
        polls: dict[HouseId, ActivePoll] = {}
        for house_id, poll_id, title, ends_at, voted in result.tuples().all():
            polls.setdefault(
                HouseId(house_id),
                ActivePoll(
                    poll_id=PollId(poll_id),
                    title=title,
                    ends_at=ends_at,
                    voted_flats=voted,
                ),
            )
        return polls

    async def appointments_between(
        self,
        org_id: OrgId,
        since: datetime,
        until: datetime,
    ) -> dict[HouseId, int]:
        a = appointments_table.c
        stmt = scoped_to_org(
            select(a.house_id, func.count())
            .where(
                a.status == AppointmentStatus.BOOKED,
                a.starts_at >= since,
                a.starts_at < until,
            )
            .group_by(a.house_id),
            a.house_id,
            org_id,
        )
        result = await self._session.execute(stmt)
        return {HouseId(house_id): count for house_id, count in result.tuples().all()}

    async def verified_by_house(
        self,
        house_ids: Collection[HouseId],
    ) -> dict[HouseId, int]:
        if not house_ids:
            return {}
        stmt = (
            select(residents_table.c.house_id, func.count())
            .where(
                residents_table.c.house_id.in_(house_ids),
                residents_table.c.verified_at.is_not(None),
            )
            .group_by(residents_table.c.house_id)
        )
        result = await self._session.execute(stmt)
        return {HouseId(house_id): count for house_id, count in result.tuples().all()}

    async def pending_by_house(
        self,
        house_ids: Collection[HouseId],
    ) -> dict[HouseId, int]:
        if not house_ids:
            return {}
        v = flat_verification_requests_table.c
        stmt = (
            select(flats_table.c.house_id, func.count())
            .select_from(flat_verification_requests_table)
            .join(flats_table, flats_table.c.id == v.flat_id)
            .where(
                flats_table.c.house_id.in_(house_ids),
                v.status == VerificationStatus.PENDING,
            )
            .group_by(flats_table.c.house_id)
        )
        result = await self._session.execute(stmt)
        return {HouseId(house_id): count for house_id, count in result.tuples().all()}
