import secrets
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    add_resident,
    add_user,
    admin_requests_service,
    chat_cards_service,
    events_of,
    polls_service,
    reminders_service,
    requests_service,
)
from tests.test_requests import _mark_done, _mark_on_review, _member, _neighbour

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core import texts
from zheka.core.enums import (
    ChatCardKind,
    ChatStatus,
    EventType,
    OrgRole,
    PollAuthor,
    RequestCategory,
    RequestStatus,
)
from zheka.core.errors import EntityNotFound, InvalidState
from zheka.core.ids import HouseId, MaxChatId, RequestGroupId
from zheka.core.models import Chat, Flat, Request
from zheka.core.services.polls import PollCardData, PollDraft
from zheka.core.services.requests import RequestDraft
from zheka.infra.database.repos.houses import HousesRepo
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


def _syncs(
    broker: RecordingBroker,
    kind: ChatCardKind = ChatCardKind.GROUP,
) -> list[dict[str, object]]:
    return [
        sync
        for sync in broker.enqueued(TaskName.SYNC_CHAT_CARD)
        if sync["kind"] == kind
    ]


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
    cards = chat_cards_service(session)

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
    assert _syncs(broker, ChatCardKind.REQUEST) == [
        {"kind": ChatCardKind.REQUEST, "ref_id": member.id, "post": False},
    ]


async def _bind_chat(session: AsyncSession, house_id: HouseId) -> MaxChatId:
    chat_id = MaxChatId(-secrets.randbits(40))
    session.add(
        Chat(
            chat_id=chat_id,
            house_id=house_id,
            title="Дом",
            bound_at=datetime.now(UTC),
            bot_is_admin=True,
            status=ChatStatus.ACTIVE,
        ),
    )
    await session.flush()
    return chat_id


async def _own_request(session: AsyncSession, own: OrgHouseFlatUser) -> Request:
    card = await requests_service(session).create(
        own.user_id,
        own.house_id,
        RequestDraft(category=RequestCategory.ELEVATOR, description="Кв. 987, лифт"),
    )
    return card.request


@pytest.mark.parametrize("bound", [True, False])
async def test_sharing_posts_the_card_only_where_the_house_has_a_chat(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
    bound: bool,
) -> None:
    request = await _own_request(session, own)
    if bound:
        await _bind_chat(session, own.house_id)

    shared = await requests_service(session, publisher).share_to_chat(
        own.user_id,
        request.id,
    )
    await publisher.flush()

    assert shared.posted is bound
    card = {"kind": ChatCardKind.REQUEST, "ref_id": request.id, "post": True}
    assert _syncs(broker, ChatCardKind.REQUEST) == ([card] if bound else [])
    [event] = await events_of(session, EventType.REQUEST_SHARED)
    assert event.payload["channel"] == ("chat" if bound else "share")


async def test_a_grouped_request_shares_the_group_card(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    group_id = await _grouped(session, own, publisher)
    await _bind_chat(session, own.house_id)
    member = (await RequestsRepo(session).list_for_group(group_id))[0]
    assert member.author_user_id is not None
    await publisher.flush()
    broker.messages.clear()

    await requests_service(session, publisher).share_to_chat(
        member.author_user_id,
        member.id,
    )
    await publisher.flush()

    assert _syncs(broker) == [
        {"kind": ChatCardKind.GROUP, "ref_id": group_id, "post": True},
    ]


async def test_only_the_author_shares_an_open_request(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _own_request(session, own)
    neighbour = await _neighbour(session, own.house_id, "2")
    service = requests_service(session)

    with pytest.raises(EntityNotFound):
        await service.share_to_chat(neighbour, request.id)
    await _mark_on_review(session, request.id)
    with pytest.raises(InvalidState):
        await service.share_to_chat(own.user_id, request.id)
    await _mark_done(session, request.id)
    with pytest.raises(InvalidState):
        await service.share_to_chat(own.user_id, request.id)


async def test_the_request_card_hides_the_flat_and_closes_on_review(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _own_request(session, own)
    house = await HousesRepo(session).get(own.house_id)
    assert house is not None
    cards = chat_cards_service(session)

    view = await cards.render(ChatCardKind.REQUEST, request.id)

    assert view is not None
    assert view.text == texts.request_card(request, house)
    assert view.text.startswith(f"🛗 Заявка №{request.id} · Лифт\nСтатус: новая\n⏰")
    assert "987" not in view.text
    assert view.me_too is RequestCategory.ELEVATOR
    assert view.join is True

    await _mark_on_review(session, request.id)
    done = await cards.render(ChatCardKind.REQUEST, request.id)

    assert done is not None
    assert done.text == texts.request_card_done(request.id)
    assert (done.me_too, done.join) == (None, False)


async def test_a_grouped_request_card_points_to_the_group(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    publisher: TaskPublisher,
) -> None:
    group_id = await _grouped(session, own, publisher)
    member = (await RequestsRepo(session).list_for_group(group_id))[0]
    cards = chat_cards_service(session)

    view = await cards.render(ChatCardKind.REQUEST, member.id)

    assert view is not None
    assert view.text == texts.request_card_grouped(member.id, RequestCategory.LEAK)
    assert (view.me_too, view.join) == (None, False)


async def test_a_status_change_and_grouping_sync_the_request_card(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    request = await _own_request(session, own)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)

    await admin_requests_service(session, publisher).change_status(
        own.org_id,
        request.id,
        RequestStatus.ACCEPTED,
        None,
        staff,
    )
    await publisher.flush()
    moved = _syncs(broker, ChatCardKind.REQUEST)
    broker.messages.clear()
    group_id = await _grouped(session, own, publisher)
    await publisher.flush()

    assert moved == [
        {"kind": ChatCardKind.REQUEST, "ref_id": request.id, "post": False},
    ]
    members = await RequestsRepo(session).list_for_group(group_id)
    synced = {sync["ref_id"] for sync in _syncs(broker, ChatCardKind.REQUEST)}
    assert synced == {member.id for member in members}


def _poll_draft(*, is_multiple: bool = False) -> PollDraft:
    return PollDraft(
        title="Ставим шлагбаум?",
        description=None,
        options=["Да", "Нет"],
        ends_at=datetime.now(UTC) + timedelta(days=3),
        is_multiple=is_multiple,
    )


async def _staff_poll(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    publisher: TaskPublisher,
    *,
    is_multiple: bool = False,
) -> tuple[OrgHouseFlatUser, PollCardData]:
    staff = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    card = await polls_service(session, publisher).create(
        staff.user_id,
        staff.house_id,
        _poll_draft(is_multiple=is_multiple),
        org_id=staff.org_id,
    )
    return staff, card


async def test_a_poll_card_is_posted_on_create_and_synced_on_vote_and_close(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    staff, card = await _staff_poll(session, make_org_house_flat_user, publisher)
    voter = await add_user(session, "Сосед")
    await add_resident(session, voter, staff.house_id, staff.flat_id)
    service = polls_service(session, publisher)

    counted = await service.vote_in_chat(card.poll.id, voter, card.options[0].id)
    await publisher.flush()
    await service.close(card.poll.id, staff.user_id)
    await publisher.flush()

    assert counted is True
    poll = {"kind": ChatCardKind.POLL, "ref_id": card.poll.id}
    assert _syncs(broker, ChatCardKind.POLL) == [
        {**poll, "post": True},
        {**poll, "post": False},
        {**poll, "post": False},
    ]
    [voted] = await events_of(session, EventType.POLL_VOTED)
    assert voted.payload["source"] == "chat"


async def test_expired_polls_sync_their_cards(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    _, card = await _staff_poll(session, make_org_house_flat_user, publisher)
    await publisher.flush()
    broker.messages.clear()

    closed = await reminders_service(session, publisher).close_expired_polls(
        datetime.now(UTC) + timedelta(days=4),
    )
    await publisher.flush()

    assert closed >= 1
    assert {
        "kind": ChatCardKind.POLL,
        "ref_id": card.poll.id,
        "post": False,
    } in _syncs(broker, ChatCardKind.POLL)


@pytest.mark.parametrize("is_multiple", [False, True])
async def test_the_poll_card_counts_flats_and_area_and_closes_without_buttons(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    publisher: TaskPublisher,
    is_multiple: bool,
) -> None:
    staff, card = await _staff_poll(
        session,
        make_org_house_flat_user,
        publisher,
        is_multiple=is_multiple,
    )
    flat = await HousesRepo(session).get_flat(staff.flat_id)
    assert flat is not None
    flat.area = 5000
    second = Flat(house_id=staff.house_id, number="2", area=15000)
    session.add(second)
    await session.flush()
    voter = await add_user(session, "Сосед")
    await add_resident(session, voter, staff.house_id, staff.flat_id)
    await polls_service(session).vote(card.poll.id, voter, [card.options[0].id])
    cards = chat_cards_service(session)

    view = await cards.render(ChatCardKind.POLL, card.poll.id)

    assert view is not None
    lines = view.text.split("\n")
    assert lines[:3] == [
        "🗳 Опрос УК: Ставим шлагбаум?",
        "1. Да - 1 кв., 25% площади",
        "2. Нет - 0 кв., 0% площади",
    ]
    assert lines[3].startswith("Проголосовало 1 из 2 квартир, до ")
    assert lines[-2:] == [texts.POLL_NOT_OSS, texts.POLL_HASHTAG]
    assert len(view.votes) == (0 if is_multiple else 2)
    assert view.app_path == (f"/meetings/{card.poll.id}" if is_multiple else None)

    await polls_service(session).close(card.poll.id, staff.user_id)
    closed = await cards.render(ChatCardKind.POLL, card.poll.id)

    assert closed is not None
    assert closed.text.startswith("🗳 Опрос УК завершен: Ставим шлагбаум?")
    assert "до " not in closed.text.split("\n")[3]
    assert (closed.votes, closed.app_path, closed.join) == ((), None, True)


def test_a_long_option_is_cut_on_its_button() -> None:
    label = texts.vote_button(2, "Очень длинный вариант ответа, который не влезет")

    assert len(label) == texts.VOTE_OPTION_LIMIT
    assert label.startswith("2. Очень")
    assert label.endswith("…")


@pytest.mark.parametrize(
    ("total", "words"),
    [
        (1, "из 1 квартиры"),
        (2, "из 2 квартир"),
        (11, "из 11 квартир"),
        (21, "из 21 квартиры"),
    ],
)
def test_the_poll_card_counts_voters_out_of_flats_in_russian(
    total: int,
    words: str,
) -> None:
    text = texts.poll_card("Шлагбаум?", PollAuthor.CHAIRMAN, [], 0, total, None)

    assert f"Проголосовало 0 {words}\n" in text
