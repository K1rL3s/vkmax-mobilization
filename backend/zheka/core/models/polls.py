from datetime import datetime

from zheka.base import UNSET, ZhekaMutableType
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


class Poll(ZhekaMutableType):
    id: PollId = UNSET
    created_at: datetime = UNSET
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
    reminder_sent_at: datetime | None = None

    def effective_status(self, now: datetime) -> PollStatus:
        if self.status is PollStatus.CLOSED or self.ends_at <= now:
            return PollStatus.CLOSED
        return PollStatus.ACTIVE


class PollOption(ZhekaMutableType):
    id: PollOptionId = UNSET
    poll_id: PollId
    text: str
    position: int


class PollVote(ZhekaMutableType):
    id: PollVoteId = UNSET
    created_at: datetime = UNSET
    poll_id: PollId
    option_id: PollOptionId
    user_id: UserId
    resident_id: ResidentId | None = None
    flat_id: FlatId | None = None
    counted_by_area: bool
