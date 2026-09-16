from datetime import datetime
from typing import cast

from zheka.base import ZhekaMutableType
from zheka.core.enums import PollStatus
from zheka.core.ids import (
    FlatId,
    HouseId,
    OrgId,
    PollId,
    PollOptionId,
    PollVoteId,
    ResidentId,
    UserId,
)

_UNSET_AT = cast(datetime, None)
_UNSET_POLL_ID = cast(PollId, None)
_UNSET_POLL_OPTION_ID = cast(PollOptionId, None)
_UNSET_POLL_VOTE_ID = cast(PollVoteId, None)


class Poll(ZhekaMutableType):
    id: PollId = _UNSET_POLL_ID
    created_at: datetime = _UNSET_AT
    house_id: HouseId
    org_id: OrgId | None = None
    created_by_user_id: UserId
    created_by_role: str
    title: str
    description: str | None = None
    is_multiple: bool = False
    starts_at: datetime
    ends_at: datetime
    status: PollStatus


class PollOption(ZhekaMutableType):
    id: PollOptionId = _UNSET_POLL_OPTION_ID
    poll_id: PollId
    text: str
    position: int


class PollVote(ZhekaMutableType):
    id: PollVoteId = _UNSET_POLL_VOTE_ID
    created_at: datetime = _UNSET_AT
    poll_id: PollId
    option_id: PollOptionId
    user_id: UserId
    resident_id: ResidentId
    flat_id: FlatId | None = None
    counted_by_area: bool
