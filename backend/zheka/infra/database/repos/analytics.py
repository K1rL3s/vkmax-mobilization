from collections.abc import Callable, Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    Integer,
    Numeric,
    Select,
    and_,
    case,
    cast,
    exists,
    func,
    or_,
    select,
)
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from zheka.base import ZhekaType
from zheka.core.enums import (
    AnalyticsMetric,
    EventType,
    OrgRole,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestStatus,
)
from zheka.core.ids import HouseId, OrgId, UserId
from zheka.core.models import House
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.repos.requests import overdue_at
from zheka.infra.database.repos.scopes import scoped_to_org
from zheka.infra.database.tables.events import events_table
from zheka.infra.database.tables.houses import flats_table, houses_table
from zheka.infra.database.tables.meters import meters_table, readings_table
from zheka.infra.database.tables.organizations import (
    org_members_table,
    organizations_table,
)
from zheka.infra.database.tables.requests import requests_table
from zheka.infra.database.tables.residents import demand_signals_table
from zheka.infra.database.tables.users import users_table

_R = requests_table.c
_REVIEWED = _R.reviewed_at.is_not(None)
_ON_TIME = _R.reviewed_at <= _R.deadline_at


def share(part: Any, whole: Any) -> ColumnElement[int]:
    return cast(func.round(part * 10000 / func.nullif(whole, 0)), Integer)


def _seconds(since: Any, until: Any) -> ColumnElement[Any]:
    return func.extract("epoch", until - since)


def _median_minutes(seconds: Any) -> ColumnElement[int]:
    median = func.percentile_cont(0.5).within_group(seconds)
    return cast(func.round(cast(median, Numeric) / 60), Integer)


def _median(value: Any) -> ColumnElement[int]:
    median = func.percentile_cont(0.5).within_group(value)
    return cast(func.round(cast(median, Numeric)), Integer)


_METRICS: dict[AnalyticsMetric, Callable[[datetime], ColumnElement[int]]] = {
    AnalyticsMetric.ACCEPT_TIME: lambda _: cast(
        func.round(func.avg(_seconds(_R.created_at, _R.accepted_at)) / 60),
        Integer,
    ),
    AnalyticsMetric.OVERDUE_SHARE: lambda now: share(
        func.count().filter(overdue_at(now)),
        func.count(),
    ),
    AnalyticsMetric.REPEAT_SHARE: lambda _: share(
        func.count().filter(_R.parent_request_id.is_not(None)),
        func.count(),
    ),
    AnalyticsMetric.AUTO_CLOSED_SHARE: lambda _: share(
        func.count().filter(
            _R.completion_reason == RequestCompletionReason.AUTO_CLOSED,
        ),
        func.count().filter(_R.status == RequestStatus.DONE),
    ),
    AnalyticsMetric.DIGITAL_SHARE: lambda _: share(
        func.count().filter(_R.channel != RequestChannel.PHONE),
        func.count(),
    ),
    AnalyticsMetric.RATING: lambda _: cast(
        func.round(func.avg(_R.rating) * 100),
        Integer,
    ),
    AnalyticsMetric.ON_TIME_SHARE: lambda _: share(
        func.count().filter(_ON_TIME),
        func.count().filter(_REVIEWED),
    ),
    AnalyticsMetric.ACCEPT_TIME_MEDIAN: lambda _: _median_minutes(
        _seconds(_R.created_at, _R.accepted_at),
    ),
}


def _created_in(since: datetime, until: datetime) -> ColumnElement[bool]:
    return and_(_R.created_at >= since, _R.created_at < until)


def _org_requests[SelectT: Select[Any]](
    stmt: SelectT,
    org_id: OrgId,
    house_id: HouseId | None,
) -> SelectT:
    stmt = scoped_to_org(stmt, _R.house_id, org_id)
    if house_id is not None:
        stmt = stmt.where(_R.house_id == house_id)
    return stmt


class Tiles(ZhekaType):
    active: int
    overdue: int
    accept_time: int | None
    accept_time_median: int | None
    repeat_share: int | None


class SeasonCount(ZhekaType):
    flats_total: int
    submitted: int
    percent: int


class ExecutorRow(ZhekaType):
    user_id: UserId
    name: str
    closed: int
    repeat_share: int
    median_time: int | None
    rating: int | None


class ChannelRow(ZhekaType):
    channel: RequestChannel
    count: int
    share: int


class RankRow(ZhekaType):
    value: int
    median: int
    rank: int
    total: int


class CutRow(ZhekaType):
    region: str
    city: str | None
    orgs_count: int
    value: int


class PublicStats(ZhekaType):
    closed: int
    on_time: int
    on_time_share: int | None
    accept_time: int | None
    accept_time_median: int | None
    rating: int | None
    ratings_count: int


class AnalyticsRepo(BaseAlchemyRepo):
    async def tiles(
        self,
        org_id: OrgId,
        house_id: HouseId | None,
        since: datetime,
        until: datetime,
        now: datetime,
    ) -> Tiles:
        stmt = _org_requests(
            select(
                func.count().filter(_R.status != RequestStatus.DONE),
                func.count().filter(overdue_at(now)),
            ).select_from(requests_table),
            org_id,
            house_id,
        )
        result = await self._session.execute(stmt)
        active, overdue = result.tuples().one()
        period_stmt = _org_requests(
            select(
                _METRICS[AnalyticsMetric.ACCEPT_TIME](now),
                _METRICS[AnalyticsMetric.ACCEPT_TIME_MEDIAN](now),
                _METRICS[AnalyticsMetric.REPEAT_SHARE](now),
            ).where(_created_in(since, until)),
            org_id,
            house_id,
        )
        period_result = await self._session.execute(period_stmt)
        accept_time, accept_time_median, repeat_share = period_result.tuples().one()
        return Tiles(
            active=active,
            overdue=overdue,
            accept_time=accept_time,
            accept_time_median=accept_time_median,
            repeat_share=repeat_share,
        )

    async def by_category(
        self,
        org_id: OrgId,
        house_id: HouseId | None,
        since: datetime,
        until: datetime,
    ) -> list[tuple[RequestCategory, int]]:
        count = func.count()
        stmt = _org_requests(
            select(_R.category, count)
            .where(_created_in(since, until))
            .group_by(_R.category)
            .order_by(count.desc(), _R.category),
            org_id,
            house_id,
        )
        result = await self._session.execute(stmt)
        return list(result.tuples().all())

    async def by_week(
        self,
        org_id: OrgId,
        house_id: HouseId | None,
        since: datetime,
        timezone: str,
    ) -> dict[date, int]:
        week = cast(
            func.date_trunc("week", func.timezone(timezone, _R.created_at)),
            Date,
        )
        stmt = _org_requests(
            select(week, func.count()).where(_R.created_at >= since).group_by(week),
            org_id,
            house_id,
        )
        result = await self._session.execute(stmt)
        return dict(result.tuples().all())

    async def season(self, org_id: OrgId, period: date) -> dict[HouseId, SeasonCount]:
        has_meter = exists().where(meters_table.c.flat_id == flats_table.c.id)
        submitted = exists().where(
            meters_table.c.flat_id == flats_table.c.id,
            readings_table.c.meter_id == meters_table.c.id,
            readings_table.c.period == period,
        )
        done = func.count().filter(submitted)
        total = func.count()
        stmt = scoped_to_org(
            select(flats_table.c.house_id, total, done, share(done, total))
            .where(has_meter)
            .group_by(flats_table.c.house_id),
            flats_table.c.house_id,
            org_id,
        )
        result = await self._session.execute(stmt)
        return {
            HouseId(house_id): SeasonCount(
                flats_total=total,
                submitted=submitted_count,
                percent=percent,
            )
            for house_id, total, submitted_count, percent in result.tuples().all()
        }

    async def by_executor(
        self,
        org_id: OrgId,
        since: datetime,
        until: datetime,
    ) -> list[ExecutorRow]:
        e = events_table.c
        assigned_at = (
            select(func.max(e.created_at))
            .where(
                e.type == EventType.REQUEST_ASSIGNED.value,
                e.payload["request_id"].as_integer() == _R.id,
            )
            .scalar_subquery()
        )
        closed = and_(
            _R.status == RequestStatus.DONE,
            _R.done_at >= since,
            _R.done_at < until,
        )
        child = aliased(requests_table)
        repeated = exists().where(child.c.parent_request_id == _R.id)
        closed_count = func.count().filter(closed)
        reviewed = case(
            (
                and_(
                    _R.reviewed_at >= since,
                    _R.reviewed_at < until,
                    assigned_at <= _R.reviewed_at,
                ),
                _seconds(assigned_at, _R.reviewed_at),
            ),
        )
        per_executor = scoped_to_org(
            select(
                _R.executor_user_id.label("user_id"),
                closed_count.label("closed"),
                share(func.count().filter(and_(closed, repeated)), closed_count).label(
                    "repeat_share",
                ),
                _median_minutes(reviewed).label("median_time"),
                cast(
                    func.round(func.avg(case((closed, _R.rating))) * 100),
                    Integer,
                ).label("rating"),
            )
            .where(_R.executor_user_id.is_not(None))
            .group_by(_R.executor_user_id),
            _R.house_id,
            org_id,
        ).subquery()
        stmt = (
            select(
                users_table.c.id,
                users_table.c.name,
                func.coalesce(per_executor.c.closed, 0),
                func.coalesce(per_executor.c.repeat_share, 0),
                per_executor.c.median_time,
                per_executor.c.rating,
            )
            .select_from(
                org_members_table.join(
                    users_table,
                    users_table.c.id == org_members_table.c.user_id,
                ).outerjoin(
                    per_executor,
                    per_executor.c.user_id == org_members_table.c.user_id,
                ),
            )
            .where(
                org_members_table.c.org_id == org_id,
                org_members_table.c.role == OrgRole.EXECUTOR,
            )
            .order_by(users_table.c.name, users_table.c.id)
        )
        result = await self._session.execute(stmt)
        return [
            ExecutorRow(
                user_id=UserId(user_id),
                name=name,
                closed=closed_total,
                repeat_share=repeat_share,
                median_time=median_time,
                rating=rating,
            )
            for (
                user_id,
                name,
                closed_total,
                repeat_share,
                median_time,
                rating,
            ) in result.tuples().all()
        ]

    async def by_channel(
        self,
        org_id: OrgId,
        since: datetime,
        until: datetime,
    ) -> list[ChannelRow]:
        count = func.count()
        stmt = _org_requests(
            select(_R.channel, count, share(count, func.sum(count).over()))
            .where(_created_in(since, until))
            .group_by(_R.channel),
            org_id,
            None,
        )
        result = await self._session.execute(stmt)
        return [
            ChannelRow(channel=channel, count=total, share=channel_share)
            for channel, total, channel_share in result.tuples().all()
        ]

    async def org_rank(
        self,
        org_id: OrgId,
        metric: AnalyticsMetric,
        *,
        lower_is_better: bool,
        is_demo: bool,
        since: datetime,
        now: datetime,
    ) -> RankRow | None:
        peers = _peers(metric, is_demo, since, now)
        order = peers.c.value.asc() if lower_is_better else peers.c.value.desc()
        ranked = select(
            peers.c.org_id,
            peers.c.value,
            func.rank().over(order_by=order).label("rank"),
            func.count().over().label("total"),
        ).subquery()
        median = select(_median(peers.c.value)).scalar_subquery()
        stmt = select(ranked.c.value, median, ranked.c.rank, ranked.c.total).where(
            ranked.c.org_id == org_id,
        )
        result = await self._session.execute(stmt)
        row = result.tuples().one_or_none()
        if row is None:
            return None
        value, median_value, rank, total = row
        return RankRow(value=value, median=median_value, rank=rank, total=total)

    async def cuts(
        self,
        metric: AnalyticsMetric,
        *,
        is_demo: bool,
        min_orgs: int,
        since: datetime,
        now: datetime,
    ) -> list[CutRow]:
        rows: list[CutRow] = []
        by_region = [houses_table.c.region]
        for cut in (by_region, [*by_region, houses_table.c.city]):
            peers = _peers(metric, is_demo, since, now, *cut)
            orgs_count = func.count()
            keys = [peers.c[column.name] for column in cut]
            complements = []
            for depth in range(len(cut)):
                parent = _peers(metric, is_demo, since, now, *cut[:depth])
                parent_count = (
                    select(func.count())
                    .select_from(parent)
                    .where(
                        *[
                            parent.c[column.name] == peers.c[column.name]
                            for column in cut[:depth]
                        ],
                    )
                    .scalar_subquery()
                )
                complement = parent_count - orgs_count
                complements.append(or_(complement == 0, complement >= min_orgs))
            stmt = (
                select(*keys, orgs_count, _median(peers.c.value))
                .group_by(*keys)
                .having(orgs_count >= min_orgs, *complements)
                .order_by(*keys)
            )
            result = await self._session.execute(stmt)
            for row in result.tuples().all():
                region, *city, count, value = row
                rows.append(
                    CutRow(
                        region=region,
                        city=city[0] if city else None,
                        orgs_count=count,
                        value=value,
                    ),
                )
        return rows

    async def unconnected_houses(self, limit: int) -> Sequence[tuple[House, int]]:
        waiting = func.count(demand_signals_table.c.id)
        stmt = (
            select(House, waiting)
            .select_from(
                houses_table.join(
                    demand_signals_table,
                    demand_signals_table.c.house_id == houses_table.c.id,
                ).outerjoin(
                    organizations_table,
                    organizations_table.c.id == houses_table.c.org_id,
                ),
            )
            .where(
                or_(
                    houses_table.c.org_id.is_(None),
                    organizations_table.c.registered_at.is_(None),
                ),
            )
            .group_by(houses_table.c.id)
            .order_by(waiting.desc(), houses_table.c.id)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.tuples().all())

    async def public_stats(
        self,
        org_id: OrgId,
        since: datetime,
        now: datetime,
    ) -> PublicStats:
        stmt = _org_requests(
            select(
                func.count().filter(_REVIEWED),
                func.count().filter(_ON_TIME),
                _METRICS[AnalyticsMetric.ON_TIME_SHARE](now),
                _METRICS[AnalyticsMetric.ACCEPT_TIME](now),
                _METRICS[AnalyticsMetric.ACCEPT_TIME_MEDIAN](now),
                _METRICS[AnalyticsMetric.RATING](now),
                func.count(_R.rating),
            ).where(_created_in(since, now)),
            org_id,
            None,
        )
        result = await self._session.execute(stmt)
        (
            closed,
            on_time,
            on_time_share,
            accept_time,
            accept_time_median,
            rating,
            ratings_count,
        ) = result.tuples().one()
        return PublicStats(
            closed=closed,
            on_time=on_time,
            on_time_share=on_time_share,
            accept_time=accept_time,
            accept_time_median=accept_time_median,
            rating=rating,
            ratings_count=ratings_count,
        )


def _peers(
    metric: AnalyticsMetric,
    is_demo: bool,
    since: datetime,
    now: datetime,
    *cut: Any,
) -> Any:
    value = _METRICS[metric](now)
    stmt = (
        select(houses_table.c.org_id, *cut, value.label("value"))
        .select_from(
            requests_table.join(houses_table, houses_table.c.id == _R.house_id).join(
                organizations_table,
                organizations_table.c.id == houses_table.c.org_id,
            ),
        )
        .where(
            organizations_table.c.is_demo == is_demo,
            organizations_table.c.registered_at.is_not(None),
            _created_in(since, now),
        )
        .group_by(houses_table.c.org_id, *cut)
        .having(value.is_not(None))
    )
    return stmt.subquery()
