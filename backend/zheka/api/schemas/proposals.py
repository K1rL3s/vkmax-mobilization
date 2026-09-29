from datetime import datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import ProposalStatus
from zheka.core.ids import CouncilProposalId, PollId
from zheka.core.services.proposals import (
    TEXT_MAX,
    TEXT_MIN,
    MyProposals,
    ProposalView,
)

ProposalText = Field(min_length=TEXT_MIN, max_length=TEXT_MAX)


class ProposalItem(BaseSchema):
    id: CouncilProposalId
    created_at: datetime
    text: str
    status: ProposalStatus
    answer: str | None
    answered_at: datetime | None
    poll_id: PollId | None

    @classmethod
    def of(cls, view: ProposalView) -> Self:
        return cls(
            id=view.id,
            created_at=view.created_at,
            text=view.text,
            status=view.status,
            answer=view.answer,
            answered_at=view.answered_at,
            poll_id=view.poll_id,
        )


class MyProposalsResponse(BaseSchema):
    has_chairman: bool
    items: list[ProposalItem]

    @classmethod
    def of(cls, view: MyProposals) -> Self:
        return cls(
            has_chairman=view.has_chairman,
            items=[ProposalItem.of(item) for item in view.items],
        )


class CreateProposalRequest(BaseSchema):
    text: str = ProposalText


class AnswerProposalRequest(BaseSchema):
    accepted: bool
    answer: str | None = Field(default=None, max_length=TEXT_MAX)
    poll_id: PollId | None = None
