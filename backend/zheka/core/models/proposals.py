from datetime import datetime

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.enums import ProposalStatus
from zheka.core.ids import CouncilProposalId, HouseId, PollId, UserId


class CouncilProposal(ZhekaMutableType):
    id: CouncilProposalId = UNSET
    created_at: datetime = UNSET
    house_id: HouseId
    author_user_id: UserId
    text: str
    status: ProposalStatus = ProposalStatus.NEW
    answer: str | None = None
    answered_at: datetime | None = None
    poll_id: PollId | None = None
