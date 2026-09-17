from collections.abc import Collection, Sequence
from datetime import datetime

from sqlalchemy import func, select

from zheka.core.enums import (
    RequestCategory,
    RequestChannel,
    RequestPhotoKind,
    RequestStatus,
)
from zheka.core.ids import (
    FlatId,
    HouseId,
    RequestGroupId,
    RequestId,
    UserId,
)
from zheka.infra.database.models import (
    Request,
    RequestGroup,
    RequestMessage,
    RequestPhoto,
    RequestStatusLog,
)
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.requests import (
    request_groups_table,
    request_messages_table,
    request_photos_table,
    request_status_log_table,
    requests_table,
)


class RequestsRepo(BaseAlchemyRepo):
    async def create(
        self,
        house_id: HouseId,
        flat_id: FlatId | None,
        author_user_id: UserId,
        category: RequestCategory,
        description: str,
        channel: RequestChannel,
        group_id: RequestGroupId | None,
        parent_request_id: RequestId | None,
        *,
        is_staff_author: bool,
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
        )
        self._session.add(request)
        await self._session.flush()
        return request

    async def get(self, request_id: RequestId) -> Request | None:
        stmt = select(Request).where(requests_table.c.id == request_id)
        # аннотация обязательна: Request отображен императивно, и scalar()
        # для такой сущности возвращает Any
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

        total = await self._count(stmt)
        page_stmt = (
            stmt.order_by(requests_table.c.id.desc()).limit(limit).offset(offset)
        )
        result = await self._session.execute(page_stmt)
        return result.scalars().all(), total

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
    ) -> RequestPhoto:
        photo = RequestPhoto(
            request_id=request_id,
            path=path,
            kind=kind,
            uploaded_by=uploaded_by,
        )
        self._session.add(photo)
        await self._session.flush()
        return photo

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
    ) -> RequestStatusLog:
        log = RequestStatusLog(
            request_id=request_id,
            from_status=from_status,
            to_status=to_status,
            by_user_id=by_user_id,
            by_role=by_role,
            at=at,
        )
        self._session.add(log)
        await self._session.flush()
        return log

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
    ) -> RequestMessage:
        message = RequestMessage(
            request_id=request_id,
            author_user_id=author_user_id,
            author_role=author_role,
            text=text,
        )
        self._session.add(message)
        await self._session.flush()
        return message

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
