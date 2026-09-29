from datetime import datetime, timedelta

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.enums import (
    DangerKind,
    RequestAttachmentKind,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestGroupStatus,
    RequestPlace,
    RequestStatus,
)
from zheka.core.ids import (
    FlatId,
    HouseId,
    RequestAttachmentId,
    RequestGroupId,
    RequestId,
    RequestMessageId,
    RequestStatusLogId,
    UserId,
)

WARN_SHARE = 4
WARN_MIN = timedelta(hours=1)
WARN_MAX = timedelta(hours=24)


class Request(ZhekaMutableType):
    id: RequestId = UNSET
    created_at: datetime = UNSET
    house_id: HouseId
    flat_id: FlatId | None = None
    author_user_id: UserId | None = None
    category: RequestCategory
    description: str
    status: RequestStatus
    completion_reason: RequestCompletionReason | None = None
    parent_request_id: RequestId | None = None
    group_id: RequestGroupId | None = None
    channel: RequestChannel
    caller_name: str | None = None
    caller_phone: str | None = None
    executor_user_id: UserId | None = None
    rating: int | None = None
    feedback: str | None = None
    accepted_at: datetime | None = None
    done_at: datetime | None = None
    reviewed_at: datetime | None = None
    is_staff_author: bool = False
    deadline_at: datetime
    react_deadline_at: datetime | None = None
    deadline_warned_at: datetime | None = None
    overdue_notified_at: datetime | None = None
    escalated_at: datetime | None = None
    question_asked_at: datetime | None = None
    resident_answered_at: datetime | None = None
    danger: DangerKind | None = None
    place: RequestPlace = RequestPlace.FLAT

    @property
    def warn_at(self) -> datetime:
        lead = (self.deadline_at - self.created_at) / WARN_SHARE
        return self.deadline_at - max(WARN_MIN, min(lead, WARN_MAX))

    @property
    def is_canceled(self) -> bool:
        return self.completion_reason is RequestCompletionReason.RESIDENT_CANCELED


class RequestGroup(ZhekaMutableType):
    id: RequestGroupId = UNSET
    house_id: HouseId
    category: RequestCategory
    window_started_at: datetime
    status: RequestGroupStatus


class RequestAttachment(ZhekaMutableType):
    id: RequestAttachmentId = UNSET
    created_at: datetime = UNSET
    request_id: RequestId
    path: str
    kind: RequestAttachmentKind
    uploaded_by: UserId


class RequestStatusLog(ZhekaMutableType):
    id: RequestStatusLogId = UNSET
    request_id: RequestId
    from_status: RequestStatus | None = None
    to_status: RequestStatus
    by_user_id: UserId | None = None
    by_role: str
    at: datetime


class RequestMessage(ZhekaMutableType):
    id: RequestMessageId = UNSET
    created_at: datetime = UNSET
    request_id: RequestId
    author_user_id: UserId
    author_role: str
    text: str
    is_internal: bool = False
