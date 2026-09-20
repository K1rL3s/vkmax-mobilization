from datetime import datetime, timedelta
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.files import PHOTOS_DESCRIPTION, FileRef
from zheka.core.enums import (
    CATEGORY_RULES,
    CategoryRule,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestGroupStatus,
    RequestStatus,
    ResponsibilityZone,
)
from zheka.core.ids import FlatId, HouseId, RequestGroupId, RequestId, UserId
from zheka.core.models import Request, RequestStatusLog
from zheka.core.services.admin_requests import (
    AdminRequestCardData,
    AdminRequestRow,
    ExecutorView,
    RequestGroupCardData,
)
from zheka.core.services.request_groups import SimilarRequests
from zheka.core.services.requests import (
    RequestCardData,
    RequestMessageView,
    RequestRow,
)

MIN_RATING = 1
MAX_RATING = 5


UNKNOWN_AUTHOR = "Пользователь"


class RequestCategoryItem(BaseSchema):
    category: RequestCategory
    label: str
    zone: ResponsibilityZone
    normative_hours: int

    @classmethod
    def of(cls, category: RequestCategory, rule: CategoryRule) -> Self:
        return cls(
            category=category,
            label=rule.label,
            zone=rule.zone,
            normative_hours=rule.normative_hours,
        )


def deadline_of(request: Request) -> datetime:
    # норматив реакции по категории, от момента подачи: фронт красит просрочку
    # сам, поэтому отдается срок, а не флаг
    hours = CATEGORY_RULES[request.category].normative_hours
    return request.created_at + timedelta(hours=hours)


class RequestListItem(BaseSchema):
    id: RequestId
    created_at: datetime
    category: RequestCategory
    category_label: str
    description: str
    status: RequestStatus
    channel: RequestChannel
    has_photos: bool
    group_size: int
    flat_number: str | None = None
    group_id: RequestGroupId | None = None
    executor_name: str | None = None
    rating: int | None = Field(default=None, description="Оценка жителя от 1 до 5")
    deadline_at: datetime | None = None
    completion_reason: RequestCompletionReason | None = None

    @classmethod
    def of_row(cls, row: RequestRow) -> Self:
        request = row.request
        return cls(
            id=RequestId(request.id),
            created_at=request.created_at,
            category=request.category,
            category_label=CATEGORY_RULES[request.category].label,
            description=request.description,
            status=request.status,
            channel=request.channel,
            has_photos=row.has_photos,
            group_size=row.group_size,
            flat_number=None if row.flat is None else row.flat.number,
            group_id=(
                None if request.group_id is None else RequestGroupId(request.group_id)
            ),
            executor_name=None if row.executor is None else row.executor.name,
            rating=request.rating,
            deadline_at=deadline_of(request),
            completion_reason=request.completion_reason,
        )


class RequestMessageItem(BaseSchema):
    created_at: datetime
    author_role: str
    author_name: str
    text: str

    @classmethod
    def of(cls, view: RequestMessageView) -> Self:
        return cls(
            created_at=view.message.created_at,
            author_role=view.message.author_role,
            author_name=UNKNOWN_AUTHOR if view.author is None else view.author.name,
            text=view.message.text,
        )


class RequestStatusLogItem(BaseSchema):
    at: datetime
    to_status: RequestStatus
    by_role: str
    from_status: RequestStatus | None = None

    @classmethod
    def of(cls, log: RequestStatusLog) -> Self:
        return cls(
            at=log.at,
            to_status=log.to_status,
            by_role=log.by_role,
            from_status=log.from_status,
        )


class RequestCard(RequestListItem):
    house_id: HouseId
    address: str
    org_name: str | None
    normative_hours: int
    photos: list[FileRef]
    result_photos: list[FileRef]
    messages: list[RequestMessageItem]
    timeline: list[RequestStatusLogItem]
    can_review: bool
    can_rate: bool
    feedback: str | None = None
    parent_request_id: RequestId | None = None
    flat_id: FlatId | None = None
    auto_close_at: datetime | None = Field(
        default=None,
        description="Автозакрытие заявки, оставленной на приемке",
    )

    @classmethod
    def of(
        cls,
        card: RequestCardData,
        photos: list[FileRef],
        result_photos: list[FileRef],
    ) -> Self:
        request = card.request
        return cls(
            id=RequestId(request.id),
            created_at=request.created_at,
            category=request.category,
            category_label=CATEGORY_RULES[request.category].label,
            description=request.description,
            status=request.status,
            channel=request.channel,
            has_photos=bool(photos),
            group_size=card.group_size,
            flat_number=None if card.flat is None else card.flat.number,
            group_id=(
                None if request.group_id is None else RequestGroupId(request.group_id)
            ),
            executor_name=None if card.executor is None else card.executor.name,
            rating=request.rating,
            deadline_at=deadline_of(request),
            house_id=HouseId(request.house_id),
            address=card.house.address,
            org_name=None if card.org is None else card.org.name,
            normative_hours=CATEGORY_RULES[request.category].normative_hours,
            photos=photos,
            result_photos=result_photos,
            messages=[RequestMessageItem.of(view) for view in card.messages],
            timeline=[RequestStatusLogItem.of(log) for log in card.timeline],
            can_review=card.can_review,
            can_rate=card.can_rate,
            feedback=request.feedback,
            parent_request_id=(
                None
                if request.parent_request_id is None
                else RequestId(request.parent_request_id)
            ),
            flat_id=None if request.flat_id is None else FlatId(request.flat_id),
            completion_reason=request.completion_reason,
            auto_close_at=card.auto_close_at,
        )


class CreateRequestRequest(BaseSchema):
    category: RequestCategory
    description: str
    flat_id: FlatId | None = None
    photos: list[str] = Field(default_factory=list, description=PHOTOS_DESCRIPTION)
    join_group_id: RequestGroupId | None = None
    llm_suggested: bool = False
    llm_accepted: bool = False


class SimilarRequestsResponse(BaseSchema):
    category: RequestCategory
    neighbours_count: int
    can_join: bool
    group_id: RequestGroupId | None = None
    window_started_at: datetime | None = None

    @classmethod
    def of(cls, similar: SimilarRequests) -> Self:
        return cls(
            category=similar.category,
            neighbours_count=similar.flats_count,
            # присоединиться можно к собранной группе, а не к россыпи жалоб
            can_join=similar.group_id is not None,
            group_id=similar.group_id,
            window_started_at=similar.window_started_at,
        )


class RateRequestRequest(BaseSchema):
    rating: int = Field(ge=MIN_RATING, le=MAX_RATING)
    feedback: str | None = None


class RepeatRequestRequest(BaseSchema):
    description: str | None = None
    photos: list[str] = Field(default_factory=list, description=PHOTOS_DESCRIPTION)


class RequestExport(BaseSchema):
    request: RequestCard
    org_name: str | None
    # документ юридической силы не имеет, текст рисует фронт
    disclaimer: str


class AdminRequestListItem(RequestListItem):
    house_id: HouseId
    address: str
    is_staff_author: bool
    author_name: str | None = None
    caller_name: str | None = None
    caller_phone: str | None = None

    @classmethod
    def of_admin(cls, row: AdminRequestRow) -> Self:
        base = RequestListItem.of_row(
            RequestRow(
                request=row.request,
                flat=row.flat,
                has_photos=row.has_photos,
                group_size=row.group_size,
                executor=row.executor,
            ),
        )
        request = row.request
        return cls(
            **base.model_dump(),
            house_id=HouseId(request.house_id),
            address=row.house.address,
            is_staff_author=request.is_staff_author,
            author_name=None if row.author is None else row.author.name,
            caller_name=request.caller_name,
            caller_phone=request.caller_phone,
        )


class AdminRequestCard(RequestCard):
    is_staff_author: bool
    author_name: str | None = None
    caller_name: str | None = None
    caller_phone: str | None = None
    executor_user_id: UserId | None = None

    @classmethod
    def of_admin(
        cls,
        data: AdminRequestCardData,
        photos: list[FileRef],
        result_photos: list[FileRef],
    ) -> Self:
        base = RequestCard.of(data.card, photos, result_photos)
        request = data.card.request
        return cls(
            **base.model_dump(),
            is_staff_author=request.is_staff_author,
            author_name=None if data.author is None else data.author.name,
            caller_name=request.caller_name,
            caller_phone=request.caller_phone,
            executor_user_id=(
                None
                if request.executor_user_id is None
                else UserId(request.executor_user_id)
            ),
        )


class ChangeRequestStatusRequest(BaseSchema):
    status: RequestStatus
    comment: str | None = None


class ReplyToRequestRequest(BaseSchema):
    text: str


class AssignExecutorRequest(BaseSchema):
    user_id: UserId


class CreatePhoneRequestRequest(BaseSchema):
    house_id: HouseId
    category: RequestCategory
    description: str
    flat_id: FlatId | None = None
    caller_name: str | None = None
    caller_phone: str | None = None


class RequestGroupCard(BaseSchema):
    id: RequestGroupId
    house_id: HouseId
    address: str
    category: RequestCategory
    category_label: str
    status: RequestGroupStatus
    window_started_at: datetime
    flats_count: int
    requests: list[AdminRequestListItem]

    @classmethod
    def of(cls, data: RequestGroupCardData) -> Self:
        group = data.group
        return cls(
            id=RequestGroupId(group.id),
            house_id=HouseId(group.house_id),
            address=data.house.address,
            category=group.category,
            category_label=CATEGORY_RULES[group.category].label,
            status=group.status,
            window_started_at=group.window_started_at,
            flats_count=data.flats_count,
            requests=[AdminRequestListItem.of_admin(row) for row in data.rows],
        )


class ChangeGroupStatusRequest(BaseSchema):
    status: RequestStatus
    comment: str | None = None


class ExecutorItem(BaseSchema):
    user_id: UserId
    name: str
    username: str | None
    active_requests: int

    @classmethod
    def of(cls, view: ExecutorView) -> Self:
        return cls(
            user_id=UserId(view.user.id),
            name=view.user.name,
            username=view.user.username,
            active_requests=view.active_requests,
        )
