from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from zheka.core.enums import ProposalStatus
from zheka.core.ids import CouncilProposalId, HouseId, PollId, UserId
from zheka.infra.database.models import CouncilProposal
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.proposals import council_proposals_table


class ProposalsRepo(BaseAlchemyRepo):
    async def create(
        self,
        house_id: HouseId,
        author_user_id: UserId,
        text: str,
    ) -> CouncilProposal:
        proposal = CouncilProposal(
            house_id=house_id,
            author_user_id=author_user_id,
            text=text,
            status=ProposalStatus.NEW,
        )
        self._session.add(proposal)
        await self._session.flush()
        return proposal

    async def get(self, proposal_id: CouncilProposalId) -> CouncilProposal | None:
        stmt = select(CouncilProposal).where(
            council_proposals_table.c.id == proposal_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_house(self, house_id: HouseId) -> Sequence[CouncilProposal]:
        stmt = (
            select(CouncilProposal)
            .where(council_proposals_table.c.house_id == house_id)
            .order_by(council_proposals_table.c.id.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_author(
        self,
        house_id: HouseId,
        author_user_id: UserId,
    ) -> Sequence[CouncilProposal]:
        stmt = (
            select(CouncilProposal)
            .where(
                council_proposals_table.c.house_id == house_id,
                council_proposals_table.c.author_user_id == author_user_id,
            )
            .order_by(council_proposals_table.c.id.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_since(
        self,
        house_id: HouseId,
        author_user_id: UserId,
        since: datetime,
    ) -> int:
        stmt = select(func.count()).where(
            council_proposals_table.c.house_id == house_id,
            council_proposals_table.c.author_user_id == author_user_id,
            council_proposals_table.c.created_at >= since,
        )
        return await self._session.scalar(stmt) or 0

    async def answer(
        self,
        proposal: CouncilProposal,
        status: ProposalStatus,
        answer: str | None,
        poll_id: PollId | None,
        now: datetime,
    ) -> CouncilProposal:
        proposal.status = status
        proposal.answer = answer
        proposal.poll_id = poll_id
        proposal.answered_at = now
        await self._session.flush()
        return proposal
