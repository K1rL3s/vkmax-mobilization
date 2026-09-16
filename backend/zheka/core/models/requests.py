from datetime import datetime
from typing import cast

from zheka.base import ZhekaMutableType
from zheka.core.enums import (
    RequestCategory,
    RequestChannel,
    RequestGroupStatus,
    RequestPhotoKind,
    RequestStatus,
)
from zheka.core.ids import (
    FlatId,
    HouseId,
    RequestGroupId,
    RequestId,
    RequestMessageId,
    RequestPhotoId,
    RequestStatusLogId,
    UserId,
)

_UNSET_AT = cast(datetime, None)
_UNSET_REQUEST_ID = cast(RequestId, None)
_UNSET_REQUEST_GROUP_ID = cast(RequestGroupId, None)
_UNSET_REQUEST_PHOTO_ID = cast(RequestPhotoId, None)
_UNSET_REQUEST_STATUS_LOG_ID = cast(RequestStatusLogId, None)
_UNSET_REQUEST_MESSAGE_ID = cast(RequestMessageId, None)


class Request(ZhekaMutableType):
    id: RequestId = _UNSET_REQUEST_ID
    created_at: datetime = _UNSET_AT
    house_id: HouseId
    flat_id: FlatId | None = None
    author_user_id: UserId | None = None
    category: RequestCategory
    description: str
    status: RequestStatus
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
    executor_message_id: str | None = None
    review_message_id: str | None = None


class RequestGroup(ZhekaMutableType):
    id: RequestGroupId = _UNSET_REQUEST_GROUP_ID
    house_id: HouseId
    category: RequestCategory
    window_started_at: datetime
    status: RequestGroupStatus


class RequestPhoto(ZhekaMutableType):
    id: RequestPhotoId = _UNSET_REQUEST_PHOTO_ID
    created_at: datetime = _UNSET_AT
    request_id: RequestId
    path: str
    kind: RequestPhotoKind
    uploaded_by: UserId


class RequestStatusLog(ZhekaMutableType):
    id: RequestStatusLogId = _UNSET_REQUEST_STATUS_LOG_ID
    request_id: RequestId
    from_status: RequestStatus | None = None
    to_status: RequestStatus
    by_user_id: UserId | None = None
    by_role: str
    at: datetime


class RequestMessage(ZhekaMutableType):
    id: RequestMessageId = _UNSET_REQUEST_MESSAGE_ID
    created_at: datetime = _UNSET_AT
    request_id: RequestId
    author_user_id: UserId
    author_role: str
    text: str
