import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    OrgHouseFlatUser,
    RecordingBroker,
    admin_requests_service,
    requests_service,
)
from tests.test_requests import _mark_on_review, _member, _neighbour

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core import texts
from zheka.core.enums import ChatCardKind, OrgRole, RequestCategory, RequestStatus
from zheka.core.ids import RequestGroupId
from zheka.core.services.chat_cards import ChatCardsService
from zheka.core.services.requests import RequestDraft
from zheka.infra.database.repos.requests import RequestsRepo


async def _grouped(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    publisher: TaskPublisher,
) -> RequestGroupId:
    service = requests_service(session, publisher)
    group_id = None
    for number in ("11", "12", "13"):
        card = await service.create(
            await _neighbour(session, own.house_id, number),
            own.house_id,
            RequestDraft(category=RequestCategory.LEAK, description="Течет стояк"),
        )
        group_id = card.request.group_id
    assert group_id is not None
    return group_id


def _syncs(broker: RecordingBroker) -> list[dict[str, object]]:
    return broker.enqueued(TaskName.SYNC_CHAT_CARD)


async def test_a_formed_group_and_each_join_post_the_card(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    group_id = await _grouped(session, own, publisher)
    await publisher.flush()
    formed = _syncs(broker)

    await requests_service(session, publisher).create(
        await _neighbour(session, own.house_id, "14"),
        own.house_id,
        RequestDraft(category=RequestCategory.LEAK, description="И у нас"),
    )
    await publisher.flush()

    card = {"kind": ChatCardKind.GROUP, "ref_id": group_id, "post": True}
    assert formed == [card]
    assert _syncs(broker) == [card, card]


async def test_a_group_status_change_queues_one_card_sync(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    group_id = await _grouped(session, own, publisher)
    await publisher.flush()
    broker.messages.clear()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)

    await admin_requests_service(session, publisher).change_group_status(
        own.org_id,
        group_id,
        RequestStatus.IN_PROGRESS,
        None,
        staff,
    )
    await publisher.flush()

    assert _syncs(broker) == [
        {"kind": ChatCardKind.GROUP, "ref_id": group_id, "post": False},
    ]


async def test_the_group_card_counts_flats_and_shows_the_earliest_status(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    publisher: TaskPublisher,
) -> None:
    group_id = await _grouped(session, own, publisher)
    members = await RequestsRepo(session).list_for_group(group_id)
    members[0].status = RequestStatus.IN_PROGRESS
    await session.flush()
    cards = ChatCardsService(RequestsRepo(session))

    view = await cards.render(ChatCardKind.GROUP, group_id)

    assert view is not None
    assert view.house_id == own.house_id
    assert view.text == texts.group_card(RequestCategory.LEAK, 3, RequestStatus.NEW)
    assert "сообщили 3 квартиры" in view.text
    assert view.me_too is RequestCategory.LEAK
    assert view.join is True

    for member in members:
        member.status = RequestStatus.ON_REVIEW
    await session.flush()
    done = await cards.render(ChatCardKind.GROUP, group_id)

    assert done is not None
    assert done.text == texts.group_card_done(RequestCategory.LEAK, 3)
    assert done.me_too is None
    assert done.join is False


@pytest.mark.parametrize(
    ("count", "words"),
    [
        (1, "1 квартира"),
        (2, "2 квартиры"),
        (5, "5 квартир"),
        (11, "11 квартир"),
        (14, "14 квартир"),
        (21, "21 квартира"),
        (22, "22 квартиры"),
        (112, "112 квартир"),
    ],
)
def test_flats_are_counted_in_russian(count: int, words: str) -> None:
    assert texts.flats_count(count) == words


async def test_only_a_card_sync_is_queued_once_per_transaction(
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    for _ in range(2):
        publisher.publish(TaskName.SYNC_CHAT_CARD, kind="group", ref_id=1, post=False)
        publisher.publish(TaskName.SEND_TO_USER, user_id=1, text="Привет")
    await publisher.flush()

    assert len(broker.enqueued(TaskName.SYNC_CHAT_CARD)) == 1
    assert len(broker.enqueued(TaskName.SEND_TO_USER)) == 2


async def test_an_accepted_member_of_a_group_syncs_its_card(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    group_id = await _grouped(session, own, publisher)
    await publisher.flush()
    broker.messages.clear()
    member = (await RequestsRepo(session).list_for_group(group_id))[0]
    await _mark_on_review(session, member.id)
    assert member.author_user_id is not None

    await requests_service(session, publisher).accept(member.author_user_id, member.id)
    await publisher.flush()

    assert _syncs(broker) == [
        {"kind": ChatCardKind.GROUP, "ref_id": group_id, "post": False},
    ]
