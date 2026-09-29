from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    add_resident,
    add_user,
    make_notifications_service,
    polls_service,
)

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import ProposalStatus, ResidentStatus
from zheka.core.errors import (
    EntityNotFound,
    InvalidState,
    InvalidValue,
    NotEnoughRights,
)
from zheka.core.ids import CouncilProposalId, UserId
from zheka.core.services.events import EventsService
from zheka.core.services.polls import PollDraft
from zheka.core.services.proposals import PER_DAY, ProposalsService
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.proposals import ProposalsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

TEXT = "Поставить лавочку у третьего подъезда"


def _service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
) -> ProposalsService:
    return ProposalsService(
        ProposalsRepo(session),
        ResidentsRepo(session),
        PollsRepo(session),
        make_notifications_service(session, publisher),
        EventsService(EventsRepo(session)),
    )


async def _neighbour(
    session: AsyncSession,
    base: OrgHouseFlatUser,
    *,
    is_chairman: bool = False,
    status: ResidentStatus = ResidentStatus.ACTIVE,
) -> UserId:
    user_id = await add_user(session, "Сосед")
    await add_resident(
        session,
        user_id,
        base.house_id,
        None,
        is_chairman=is_chairman,
        status=status,
    )
    return user_id


async def _house_with_chairman(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> tuple[OrgHouseFlatUser, UserId, UserId]:
    base = await make_org_house_flat_user()
    chairman = await _neighbour(session, base, is_chairman=True)
    author = await _neighbour(session, base)
    return base, chairman, author


async def test_a_proposal_reaches_the_chairman_without_its_author(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    base, chairman, author = await _house_with_chairman(
        session,
        make_org_house_flat_user,
    )
    service = _service(session, publisher)

    view = await service.propose(author, base.house_id, f"  {TEXT}  ")

    assert view.status is ProposalStatus.NEW
    assert view.text == TEXT
    await publisher.flush()
    (sent,) = broker.enqueued(TaskName.SEND_TO_USER)
    assert sent["user_id"] == chairman
    assert "Автор скрыт" in sent["text"]
    incoming = await service.list_for_chairman(chairman, base.house_id)
    assert [item.id for item in incoming] == [view.id]
    assert not hasattr(incoming[0], "author_user_id")


async def test_a_house_without_a_living_chairman_takes_no_proposal(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base = await make_org_house_flat_user()
    author = await _neighbour(session, base)
    service = _service(session)

    with pytest.raises(InvalidState):
        await service.propose(author, base.house_id, TEXT)

    await _neighbour(
        session,
        base,
        is_chairman=True,
        status=ResidentStatus.BLOCKED,
    )

    with pytest.raises(InvalidState):
        await service.propose(author, base.house_id, TEXT)

    assert (await service.list_mine(author, base.house_id)).has_chairman is False


async def test_a_short_proposal_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, _, author = await _house_with_chairman(session, make_org_house_flat_user)
    service = _service(session)

    with pytest.raises(InvalidValue):
        await service.propose(author, base.house_id, "лавочка")


async def test_a_fourth_proposal_in_a_day_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, _, author = await _house_with_chairman(session, make_org_house_flat_user)
    service = _service(session)
    for number in range(PER_DAY):
        await service.propose(author, base.house_id, f"{TEXT} {number}")

    with pytest.raises(InvalidState):
        await service.propose(author, base.house_id, f"{TEXT} еще")

    proposals = await ProposalsRepo(session).list_for_author(base.house_id, author)
    yesterday = datetime.now(UTC) - timedelta(days=1, minutes=1)
    for proposal in proposals:
        proposal.created_at = yesterday
    await session.flush()
    again = await service.propose(author, base.house_id, f"{TEXT} назавтра")
    assert again.status is ProposalStatus.NEW


async def test_only_the_chairman_reads_the_incoming_proposals(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, _, author = await _house_with_chairman(session, make_org_house_flat_user)
    service = _service(session)
    view = await service.propose(author, base.house_id, TEXT)

    with pytest.raises(NotEnoughRights):
        await service.list_for_chairman(author, base.house_id)

    mine = await service.list_mine(author, base.house_id)
    assert mine.has_chairman is True
    assert [item.id for item in mine.items] == [view.id]


async def test_a_decline_carries_an_answer_to_the_author(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    base, chairman, author = await _house_with_chairman(
        session,
        make_org_house_flat_user,
    )
    service = _service(session, publisher)
    view = await service.propose(author, base.house_id, TEXT)

    with pytest.raises(InvalidValue):
        await service.answer(view.id, chairman, "   ", None, accepted=False)

    answered = await service.answer(
        view.id,
        chairman,
        "Лавочку уже заказали",
        None,
        accepted=False,
    )

    assert answered.status is ProposalStatus.DECLINED
    assert answered.answered_at is not None
    await publisher.flush()
    reply = broker.enqueued(TaskName.SEND_TO_USER)[-1]
    assert reply["user_id"] == author
    assert reply["mandatory"] is True
    assert "Лавочку уже заказали" in reply["text"]

    with pytest.raises(InvalidState):
        await service.answer(view.id, chairman, "Передумал", None, accepted=True)


async def test_a_proposal_carried_to_a_poll_keeps_its_id(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman, author = await _house_with_chairman(
        session,
        make_org_house_flat_user,
    )
    service = _service(session)
    view = await service.propose(author, base.house_id, TEXT)
    card = await polls_service(session).create(
        chairman,
        base.house_id,
        PollDraft(
            title=TEXT,
            description=None,
            options=["За", "Против"],
            ends_at=datetime.now(UTC) + timedelta(days=3),
        ),
        org_id=None,
    )
    other = await make_org_house_flat_user()
    alien = await polls_service(session).create(
        other.user_id,
        other.house_id,
        PollDraft(
            title="Чужой опрос",
            description=None,
            options=["За", "Против"],
            ends_at=datetime.now(UTC) + timedelta(days=3),
        ),
        org_id=other.org_id,
    )

    with pytest.raises(EntityNotFound):
        await service.answer(view.id, chairman, None, alien.poll.id, accepted=True)

    with pytest.raises(InvalidValue):
        await service.answer(view.id, chairman, "Нет", card.poll.id, accepted=False)

    answered = await service.answer(
        view.id,
        chairman,
        None,
        card.poll.id,
        accepted=True,
    )

    assert answered.status is ProposalStatus.ACCEPTED
    assert answered.poll_id == card.poll.id


async def test_a_stranger_neither_proposes_nor_answers(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman, author = await _house_with_chairman(
        session,
        make_org_house_flat_user,
    )
    service = _service(session)
    view = await service.propose(author, base.house_id, TEXT)
    stranger = await add_user(session, "Прохожий")

    with pytest.raises(EntityNotFound):
        await service.propose(stranger, base.house_id, TEXT)

    with pytest.raises(EntityNotFound):
        await service.list_mine(stranger, base.house_id)

    with pytest.raises(EntityNotFound):
        await service.answer(view.id, stranger, "Нет", None, accepted=False)

    with pytest.raises(EntityNotFound):
        await service.answer(
            CouncilProposalId(view.id + 10_000),
            chairman,
            None,
            None,
            accepted=True,
        )


async def test_a_blocked_resident_proposes_nothing(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base = await make_org_house_flat_user()
    await _neighbour(session, base, is_chairman=True)
    blocked = await _neighbour(session, base, status=ResidentStatus.BLOCKED)
    service = _service(session)

    with pytest.raises(NotEnoughRights):
        await service.propose(blocked, base.house_id, TEXT)
