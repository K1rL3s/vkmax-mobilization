from collections.abc import Collection, Sequence
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from zheka.base import ZhekaType
from zheka.core.enums import (
    CATEGORY_RULES,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestGroupStatus,
    RequestPhotoKind,
    RequestStatus,
)
from zheka.core.ids import FlatId, HouseId, OrgId, RequestGroupId, RequestId, UserId
from zheka.infra.database.models import (
    Request,
    RequestGroup,
    RequestMessage,
    RequestPhoto,
    RequestStatusLog,
)
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.repos.scopes import scoped_to_org
from zheka.infra.database.tables.requests import (
    request_groups_table,
    request_messages_table,
    request_photos_table,
    request_status_log_table,
    requests_table,
)

OPEN_STATUSES = (RequestStatus.NEW, RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS)

_STAMP_BY_STATUS = {
    RequestStatus.ACCEPTED: "accepted_at",
    RequestStatus.ON_REVIEW: "reviewed_at",
    RequestStatus.DONE: "done_at",
}


class RequestFilters(ZhekaType):
    house_id: HouseId | None = None
    category: RequestCategory | None = None
    status: RequestStatus | None = None
    channel: RequestChannel | None = None
    executor_user_id: UserId | None = None
    overdue: bool = False
    grouped: bool = False


def overdue_at(now: datetime) -> ColumnElement[bool]:
    return and_(
        or_(
            *[
                and_(
                    requests_table.c.category == category,
                    requests_table.c.created_at
                    < now - timedelta(hours=rule.normative_hours),
                )
                for category, rule in CATEGORY_RULES.items()
            ],
        ),
        requests_table.c.status.not_in((RequestStatus.DONE, RequestStatus.ON_REVIEW)),
    )


class RequestsRepo(BaseAlchemyRepo):
    async def create(
        self,
        house_id: HouseId,
        flat_id: FlatId | None,
        author_user_id: UserId | None,
        category: RequestCategory,
        description: str,
        channel: RequestChannel,
        group_id: RequestGroupId | None,
        parent_request_id: RequestId | None,
        *,
        is_staff_author: bool,
        caller_name: str | None = None,
        caller_phone: str | None = None,
    ) -> Request:
        request = Request(
            house_id=house_id,
            flat_id=flat_id,
            author_user_id=author_user_id,
            category=category,
            description=description,
            status=RequestStatus.NEW,
            channel=channel,
            group_id=group_id,
            parent_request_id=parent_request_id,
            is_staff_author=is_staff_author,
            caller_name=caller_name,
            caller_phone=caller_phone,
        )
        self._session.add(request)
        await self._session.flush()
        return request

    async def get(self, request_id: RequestId) -> Request | None:
        stmt = select(Request).where(requests_table.c.id == request_id)
        request: Request | None = await self._session.scalar(stmt)
        return request

    async def list_for_user(
        self,
        user_id: UserId,
        house_id: HouseId,
        status: RequestStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Request], int]:
        stmt = select(Request).where(
            requests_table.c.author_user_id == user_id,
            requests_table.c.house_id == house_id,
        )
        if status is not None:
            stmt = stmt.where(requests_table.c.status == status)

        stmt = stmt.order_by(requests_table.c.id.desc())
        return await self._page(stmt, limit, offset)

    async def set_rating(
        self,
        request: Request,
        rating: int,
        feedback: str | None,
    ) -> None:
        request.rating = rating
        request.feedback = feedback
        await self._session.flush()

    async def add_photo(
        self,
        request_id: RequestId,
        path: str,
        kind: RequestPhotoKind,
        uploaded_by: UserId,
    ) -> None:
        self._session.add(
            RequestPhoto(
                request_id=request_id,
                path=path,
                kind=kind,
                uploaded_by=uploaded_by,
            ),
        )
        await self._session.flush()

    async def list_photos(self, request_id: RequestId) -> Sequence[RequestPhoto]:
        stmt = (
            select(RequestPhoto)
            .where(request_photos_table.c.request_id == request_id)
            .order_by(request_photos_table.c.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_photos(
        self,
        request_ids: Collection[RequestId],
    ) -> dict[RequestId, int]:
        if not request_ids:
            return {}
        stmt = (
            select(request_photos_table.c.request_id, func.count())
            .where(request_photos_table.c.request_id.in_(request_ids))
            .group_by(request_photos_table.c.request_id)
        )
        result = await self._session.execute(stmt)
        return {RequestId(request_id): count for request_id, count in result.tuples()}

    async def add_log(
        self,
        request_id: RequestId,
        from_status: RequestStatus | None,
        to_status: RequestStatus,
        by_user_id: UserId | None,
        by_role: str,
        at: datetime,
    ) -> None:
        self._session.add(
            RequestStatusLog(
                request_id=request_id,
                from_status=from_status,
                to_status=to_status,
                by_user_id=by_user_id,
                by_role=by_role,
                at=at,
            ),
        )
        await self._session.flush()

    async def list_log(self, request_id: RequestId) -> Sequence[RequestStatusLog]:
        stmt = (
            select(RequestStatusLog)
            .where(request_status_log_table.c.request_id == request_id)
            .order_by(request_status_log_table.c.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add_message(
        self,
        request_id: RequestId,
        author_user_id: UserId,
        author_role: str,
        text: str,
    ) -> None:
        self._session.add(
            RequestMessage(
                request_id=request_id,
                author_user_id=author_user_id,
                author_role=author_role,
                text=text,
            ),
        )
        await self._session.flush()

    async def list_messages(self, request_id: RequestId) -> Sequence[RequestMessage]:
        stmt = (
            select(RequestMessage)
            .where(request_messages_table.c.request_id == request_id)
            .order_by(request_messages_table.c.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_group(self, group_id: RequestGroupId) -> RequestGroup | None:
        stmt = select(RequestGroup).where(request_groups_table.c.id == group_id)
        group: RequestGroup | None = await self._session.scalar(stmt)
        return group

    async def count_by_group(
        self,
        group_ids: Collection[RequestGroupId],
    ) -> dict[RequestGroupId, int]:
        if not group_ids:
            return {}
        stmt = (
            select(requests_table.c.group_id, func.count())
            .where(requests_table.c.group_id.in_(group_ids))
            .group_by(requests_table.c.group_id)
        )
        result = await self._session.execute(stmt)
        return {RequestGroupId(group_id): count for group_id, count in result.tuples()}

    async def get_for_org(self, request_id: RequestId, org_id: OrgId) -> Request | None:
        stmt = scoped_to_org(
            select(Request).where(requests_table.c.id == request_id),
            requests_table.c.house_id,
            org_id,
        )
        request: Request | None = await self._session.scalar(stmt)
        return request

    async def list_for_org(
        self,
        org_id: OrgId,
        filters: RequestFilters,
        now: datetime,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Request], int]:
        stmt = scoped_to_org(select(Request), requests_table.c.house_id, org_id)
        for name in ("house_id", "category", "status", "channel", "executor_user_id"):
            value = getattr(filters, name)
            if value is not None:
                stmt = stmt.where(requests_table.c[name] == value)
        overdue = overdue_at(now)
        if filters.overdue:
            stmt = stmt.where(overdue)
        if filters.grouped:
            leaders = (
                select(func.min(requests_table.c.id))
                .where(requests_table.c.group_id.is_not(None))
                .group_by(requests_table.c.group_id)
            )
            stmt = stmt.where(
                or_(
                    requests_table.c.group_id.is_(None),
                    requests_table.c.id.in_(leaders),
                ),
            )

        stmt = stmt.order_by(overdue.desc(), requests_table.c.created_at.desc())
        return await self._page(stmt, limit, offset)

    async def set_status(
        self,
        request: Request,
        status: RequestStatus,
        at: datetime,
        *,
        completion_reason: RequestCompletionReason | None = None,
    ) -> None:
        request.status = status
        if status is RequestStatus.DONE:
            request.completion_reason = completion_reason
        stamp = _STAMP_BY_STATUS.get(status)
        if stamp is not None:
            setattr(request, stamp, at)
        await self._session.flush()

    async def list_reviewed_before(self, before: datetime) -> Sequence[Request]:
        stmt = (
            select(Request)
            .where(
                requests_table.c.status == RequestStatus.ON_REVIEW,
                requests_table.c.reviewed_at <= before,
            )
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def set_executor(self, request: Request, user_id: UserId) -> None:
        request.executor_user_id = user_id
        await self._session.flush()

    async def count_active_by_executor(self, org_id: OrgId) -> dict[UserId, int]:
        stmt = (
            scoped_to_org(
                select(requests_table.c.executor_user_id, func.count()),
                requests_table.c.house_id,
                org_id,
            )
            .where(
                requests_table.c.executor_user_id.is_not(None),
                requests_table.c.status.in_(OPEN_STATUSES),
            )
            .group_by(requests_table.c.executor_user_id)
        )
        result = await self._session.execute(stmt)
        return {UserId(user_id): count for user_id, count in result.tuples()}

    async def find_open_group(
        self,
        house_id: HouseId,
        category: RequestCategory,
        since: datetime,
    ) -> RequestGroup | None:
        stmt = (
            select(RequestGroup)
            .where(
                request_groups_table.c.house_id == house_id,
                request_groups_table.c.category == category,
                request_groups_table.c.status == RequestGroupStatus.OPEN,
                request_groups_table.c.window_started_at >= since,
            )
            .order_by(request_groups_table.c.id.desc())
            .limit(1)
        )
        group: RequestGroup | None = await self._session.scalar(stmt)
        return group

    async def get_group_for_org(
        self,
        group_id: RequestGroupId,
        org_id: OrgId,
    ) -> RequestGroup | None:
        stmt = scoped_to_org(
            select(RequestGroup).where(request_groups_table.c.id == group_id),
            request_groups_table.c.house_id,
            org_id,
        )
        group: RequestGroup | None = await self._session.scalar(stmt)
        return group

    async def create_group(
        self,
        house_id: HouseId,
        category: RequestCategory,
        window_started_at: datetime,
    ) -> RequestGroup:
        group = RequestGroup(
            house_id=house_id,
            category=category,
            window_started_at=window_started_at,
            status=RequestGroupStatus.OPEN,
        )
        self._session.add(group)
        await self._session.flush()
        return group

    async def set_group_status(
        self,
        group: RequestGroup,
        status: RequestGroupStatus,
    ) -> None:
        group.status = status
        await self._session.flush()

    async def list_open_in_window(
        self,
        house_id: HouseId,
        category: RequestCategory,
        since: datetime,
    ) -> Sequence[Request]:
        stmt = (
            select(Request)
            .where(
                requests_table.c.house_id == house_id,
                requests_table.c.category == category,
                requests_table.c.status.in_(OPEN_STATUSES),
                requests_table.c.created_at >= since,
            )
            .order_by(requests_table.c.created_at)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_group(self, group_id: RequestGroupId) -> Sequence[Request]:
        stmt = (
            select(Request)
            .where(requests_table.c.group_id == group_id)
            .order_by(requests_table.c.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def attach_to_group(
        self,
        requests: Sequence[Request],
        group_id: RequestGroupId,
    ) -> None:
        for request in requests:
            request.group_id = group_id
        await self._session.flush()

    async def lock(self, request: Request) -> None:
        stmt = (
            select(Request)
            .where(requests_table.c.id == request.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        await self._session.execute(stmt)

    async def last_for_flat(
        self,
        flat_id: FlatId,
        statuses: Collection[RequestStatus],
    ) -> Request | None:
        stmt = (
            select(Request)
            .where(
                requests_table.c.flat_id == flat_id,
                requests_table.c.status.in_(statuses),
            )
            .order_by(requests_table.c.id.desc())
            .limit(1)
        )
        request: Request | None = await self._session.scalar(stmt)
        return request
