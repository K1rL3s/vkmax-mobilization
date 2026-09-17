from datetime import datetime

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.files import PHOTOS_DESCRIPTION, FileRef
from zheka.core.enums import (
    RequestCategory,
    RequestChannel,
    RequestGroupStatus,
    RequestStatus,
    ResponsibilityZone,
)
from zheka.core.ids import FlatId, HouseId, RequestGroupId, RequestId, UserId

MIN_RATING = 1
MAX_RATING = 5


class RequestCategoryItem(BaseSchema):
    category: RequestCategory
    label: str
    zone: ResponsibilityZone
    normative_hours: int


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


class RequestMessageItem(BaseSchema):
    created_at: datetime
    author_role: str
    author_name: str
    text: str


class RequestStatusLogItem(BaseSchema):
    at: datetime
    to_status: RequestStatus
    by_role: str
    from_status: RequestStatus | None = None


class RequestCard(RequestListItem):
    house_id: HouseId
    address: str
    photos: list[FileRef]
    result_photos: list[FileRef]
    messages: list[RequestMessageItem]
    timeline: list[RequestStatusLogItem]
    can_review: bool
    can_rate: bool
    feedback: str | None = None
    parent_request_id: RequestId | None = None
    flat_id: FlatId | None = None


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


class RateRequestRequest(BaseSchema):
    rating: int = Field(ge=MIN_RATING, le=MAX_RATING)
    feedback: str | None = None


class RepeatRequestRequest(BaseSchema):
    description: str | None = None
    photos: list[str] = Field(default_factory=list, description=PHOTOS_DESCRIPTION)


class ReviewRequestRequest(BaseSchema):
    accepted: bool
    comment: str | None = None


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


class AdminRequestCard(RequestCard):
    is_staff_author: bool
    author_name: str | None = None
    caller_name: str | None = None
    caller_phone: str | None = None
    executor_user_id: UserId | None = None


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


class ChangeGroupStatusRequest(BaseSchema):
    status: RequestStatus
    comment: str | None = None


class ExecutorItem(BaseSchema):
    user_id: UserId
    name: str
    username: str | None
    active_requests: int
