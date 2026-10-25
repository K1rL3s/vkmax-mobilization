from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    admin_requests_service,
    chat_cards_service,
    events_of,
    requests_service,
)
from tests.test_requests import (
    _add_group,
    _age,
    _complain,
    _group_of_three,
    _member,
    _neighbour,
)

from zheka.core.enums import (
    ChatCardKind,
    EventType,
    OrgRole,
    RequestCategory,
    RequestChannel,
    RequestGroupStatus,
    RequestPlace,
    RequestStatus,
    ResidentRole,
)
from zheka.core.errors import InvalidRequest
from zheka.core.ids import FlatId, HouseId, RequestGroupId, RequestId, UserId
from zheka.core.models import Request
from zheka.core.services.admin_requests import PhoneRequestDraft
from zheka.core.services.request_groups import (
    DEFAULT_GROUP_THRESHOLD,
    DEFAULT_GROUP_WINDOW_HOURS,
    complaint_sources,
    problems_of,
)
from zheka.core.services.requests import RequestDraft
from zheka.infra.database.models import RequestGroup
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.tables.requests import request_groups_table


async def _groups(session: AsyncSession, house_id: HouseId) -> list[RequestGroup]:
    stmt = select(RequestGroup).where(request_groups_table.c.house_id == house_id)
    return list((await session.execute(stmt)).scalars().all())


async def test_three_flats_in_the_window_form_exactly_one_group(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:

    members, group_id = await _group_of_three(session, own)

    assert [group.id for group in await _groups(session, own.house_id)] == [group_id]
    assert [member.group_id for member in members] == [group_id] * 3
    formed = await events_of(session, EventType.REQUEST_GROUP_FORMED)
    assert len(formed) == 1
    assert formed[0].payload["size"] == DEFAULT_GROUP_THRESHOLD


async def test_the_fourth_request_joins_the_group_instead_of_forming_a_second(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    _, group_id = await _group_of_three(session, own)

    fourth_request = await _complain(session, own.user_id, own.house_id)

    assert len(await _groups(session, own.house_id)) == 1
    assert fourth_request.group_id == group_id
    joined = await events_of(session, EventType.REQUEST_JOINED)
    assert len(joined) == 1
    assert joined[0].payload["group_size"] == DEFAULT_GROUP_THRESHOLD + 1


async def test_a_request_outside_the_window_starts_the_count_anew(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    second = await _neighbour(session, own.house_id, "2")
    stale = [
        (await _complain(session, own.user_id, own.house_id)).id,
        (await _complain(session, second, own.house_id)).id,
    ]
    for request_id in stale:
        await _age(session, request_id, DEFAULT_GROUP_WINDOW_HOURS + 1)
    third = await _neighbour(session, own.house_id, "3")

    await _complain(session, third, own.house_id)

    assert await _groups(session, own.house_id) == []


async def test_a_group_of_another_house_is_not_joined(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _group_of_three(session, own)

    foreign = await _complain(session, other.user_id, other.house_id)

    assert foreign.group_id is None
    assert len(await _groups(session, own.house_id)) == 1


async def test_similar_counts_neighbours_without_the_asking_resident(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    second = await _neighbour(session, own.house_id, "2")
    await _complain(session, own.user_id, own.house_id)
    await _complain(session, second, own.house_id)
    service = requests_service(session)

    similar = await service.similar(own.user_id, own.house_id, RequestCategory.LEAK)

    assert similar.flats_count == 1
    assert similar.group_id is None


async def test_similar_offers_the_group_once_it_exists(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _group_of_three(session, own)
    service = requests_service(session)

    similar = await service.similar(own.user_id, own.house_id, RequestCategory.LEAK)

    assert similar.group_id is not None
    assert similar.flats_count == DEFAULT_GROUP_THRESHOLD


async def test_a_closed_group_is_not_joined(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    _, closed_id = await _group_of_three(session, own)
    [group] = await _groups(session, own.house_id)
    await RequestsRepo(session).set_group_status(group, RequestGroupStatus.CLOSED)

    fourth_request = await _complain(session, own.user_id, own.house_id)

    assert fourth_request.group_id is not None
    assert fourth_request.group_id != closed_id


async def test_three_complaints_from_one_resident_do_not_form_a_group(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:

    for _ in range(DEFAULT_GROUP_THRESHOLD):
        await _complain(session, own.user_id, own.house_id)

    assert await _groups(session, own.house_id) == []


async def test_a_formed_group_does_not_swallow_another_category(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _group_of_three(session, own)

    elevator = await _complain(
        session,
        own.user_id,
        own.house_id,
        RequestCategory.ELEVATOR,
    )

    assert elevator.group_id is None


def test_complaint_sources_count_complainants_and_not_requests() -> None:
    requests = [
        Request(
            house_id=HouseId(1),
            flat_id=flat_id,
            author_user_id=author_user_id,
            category=RequestCategory.LEAK,
            description="жалоба",
            status=RequestStatus.NEW,
            channel=RequestChannel.MINIAPP,
            deadline_at=datetime.now(UTC),
        )
        for flat_id, author_user_id in (
            (FlatId(7), None),
            (FlatId(7), None),
            (None, UserId(42)),
            (FlatId(8), UserId(43)),
        )
    ]

    assert complaint_sources(requests) == {("flat", 7), ("user", 42), ("flat", 8)}


ONE_FLAT_BILL = pytest.mark.parametrize(
    "category",
    [RequestCategory.METER_ERROR, RequestCategory.CHARGE_DISPUTE],
)


@ONE_FLAT_BILL
async def test_bill_complaints_of_three_flats_form_no_group(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    category: RequestCategory,
) -> None:
    complaints = [
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
            category,
        )
        for number in ("11", "12", "13")
    ]

    assert await _groups(session, own.house_id) == []
    assert [complaint.group_id for complaint in complaints] == [None] * 3


@ONE_FLAT_BILL
async def test_similar_counts_no_neighbours_for_a_bill_complaint(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    category: RequestCategory,
) -> None:
    second = await _neighbour(session, own.house_id, "2")
    await _complain(session, second, own.house_id, category)
    service = requests_service(session)

    similar = await service.similar(own.user_id, own.house_id, category)

    assert similar.flats_count == 0
    assert similar.window_started_at is None


@ONE_FLAT_BILL
async def test_a_bill_complaint_cannot_join_an_open_group_of_its_category(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    category: RequestCategory,
) -> None:
    group_id = await _add_group(session, own.house_id, category)

    with pytest.raises(InvalidRequest):
        await requests_service(session).create(
            own.user_id,
            own.house_id,
            RequestDraft(category=category, description="Счет", group_id=group_id),
        )


async def _two_entrances(session: AsyncSession, house_id: HouseId) -> None:
    house = await HousesRepo(session).get(house_id)
    assert house is not None
    house.entrances = 2
    await session.flush()


async def _report(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    entrance: int | None,
    category: RequestCategory = RequestCategory.ELEVATOR,
    group_id: RequestGroupId | None = None,
) -> Request:
    card = await requests_service(session).create(
        user_id,
        house_id,
        RequestDraft(
            category=category,
            description="Не работает",
            place=RequestPlace.HOUSE,
            entrance=entrance,
            group_id=group_id,
        ),
    )
    return card.request


async def test_lifts_of_one_entrance_group_and_another_entrance_stays_apart(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _two_entrances(session, own.house_id)
    members = [
        await _report(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
            1,
        )
        for number in ("11", "12", "13")
    ]
    other = await _report(session, own.user_id, own.house_id, 2)

    [group] = await _groups(session, own.house_id)
    assert group.entrance == 1
    assert [member.group_id for member in members] == [group.id] * 3
    assert other.group_id is None


async def test_lifts_of_two_entrances_do_not_add_up_to_a_group(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _two_entrances(session, own.house_id)
    for number, entrance in (("11", 1), ("12", 1), ("13", 2)):
        await _report(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
            entrance,
        )

    assert await _groups(session, own.house_id) == []


async def test_a_leak_groups_across_entrances(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _two_entrances(session, own.house_id)
    for number, entrance in (("11", 1), ("12", 2), ("13", None)):
        await _report(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
            entrance,
            RequestCategory.LEAK,
        )

    [group] = await _groups(session, own.house_id)
    assert group.entrance is None


async def test_similar_counts_lifts_of_the_asked_entrance_only(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _two_entrances(session, own.house_id)
    await _report(
        session,
        await _neighbour(session, own.house_id, "11"),
        own.house_id,
        1,
    )
    service = requests_service(session)

    first = await service.similar(
        own.user_id,
        own.house_id,
        RequestCategory.ELEVATOR,
        1,
    )
    second = await service.similar(
        own.user_id,
        own.house_id,
        RequestCategory.ELEVATOR,
        2,
    )

    assert (first.flats_count, second.flats_count) == (1, 0)


async def test_a_join_takes_the_entrance_of_the_group(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _two_entrances(session, own.house_id)
    members = [
        await _report(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
            1,
        )
        for number in ("11", "12", "13")
    ]

    joined = await _report(
        session,
        own.user_id,
        own.house_id,
        2,
        group_id=members[0].group_id,
    )

    assert joined.entrance == 1


@pytest.mark.parametrize(
    ("category", "place", "entrance"),
    [
        (RequestCategory.LEAK, RequestPlace.FLAT, 1),
        (RequestCategory.ELEVATOR, RequestPlace.HOUSE, 3),
    ],
)
async def test_an_entrance_outside_the_house_or_in_a_flat_is_refused(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    category: RequestCategory,
    place: RequestPlace,
    entrance: int,
) -> None:
    await _two_entrances(session, own.house_id)

    with pytest.raises(InvalidRequest):
        await requests_service(session).create(
            own.user_id,
            own.house_id,
            RequestDraft(
                category=category,
                description="Не работает",
                place=place,
                entrance=entrance,
            ),
        )


def test_the_board_splits_lifts_by_entrance_and_puts_the_own_entrance_first() -> None:
    def lift(request_id: int, flat_id: int, entrance: int) -> Request:
        return Request(
            id=RequestId(request_id),
            house_id=HouseId(1),
            flat_id=FlatId(flat_id),
            category=RequestCategory.ELEVATOR,
            description="лифт",
            status=RequestStatus.NEW,
            channel=RequestChannel.MINIAPP,
            deadline_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            place=RequestPlace.HOUSE,
            entrance=entrance,
        )

    board = problems_of(
        [lift(1, 7, 1), lift(2, 8, 2), lift(3, 9, 2)],
        [],
        UserId(42),
        None,
        2,
    )

    assert [(problem.entrance, problem.flats_count) for problem in board.open] == [
        (2, 2),
        (1, 1),
    ]


async def test_a_lift_without_an_entrance_takes_the_entrance_of_the_flat(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _two_entrances(session, own.house_id)
    for number in ("11", "12"):
        await _report(
            session,
            await _neighbour(session, own.house_id, number, 1),
            own.house_id,
            1,
        )
    flat = await HousesRepo(session).get_flat(own.flat_id)
    assert flat is not None
    flat.entrance = 1
    await session.flush()

    similar = await requests_service(session).similar(
        own.user_id,
        own.house_id,
        RequestCategory.ELEVATOR,
    )
    card = await requests_service(session).create(
        own.user_id,
        own.house_id,
        RequestDraft(category=RequestCategory.ELEVATOR, description="Не работает"),
        RequestChannel.BOT,
    )

    assert similar.flats_count == 2
    assert card.request.entrance == 1
    [group] = await _groups(session, own.house_id)
    assert (group.entrance, card.request.group_id) == (1, group.id)


async def test_a_phone_lift_without_an_entrance_takes_the_entrance_of_the_flat(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _two_entrances(session, own.house_id)
    flat = await HousesRepo(session).get_flat(own.flat_id)
    assert flat is not None
    flat.entrance = 2
    await session.flush()

    card = await admin_requests_service(session).create_phone(
        own.org_id,
        PhoneRequestDraft(
            house_id=own.house_id,
            category=RequestCategory.ELEVATOR,
            description="Не работает",
            flat_id=own.flat_id,
        ),
        await _member(session, own.org_id, OrgRole.EMPLOYEE),
    )

    assert card.card.request.entrance == 2


async def test_the_only_entrance_of_a_house_does_not_split_lifts(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    members = [
        await _report(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
            entrance,
        )
        for number, entrance in (("11", 1), ("12", None), ("13", None))
    ]

    [group] = await _groups(session, own.house_id)
    assert group.entrance is None
    assert [member.group_id for member in members] == [group.id] * 3
    assert members[0].entrance is None


async def test_the_chat_card_of_a_lift_group_names_its_entrance(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _two_entrances(session, own.house_id)
    for number in ("11", "12", "13"):
        await _report(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
            2,
        )
    [group] = await _groups(session, own.house_id)

    view = await chat_cards_service(session).render(ChatCardKind.GROUP, group.id)

    assert view is not None
    assert view.text.startswith("🛗 Лифт, подъезд 2: ")


@pytest.mark.parametrize(("own_entrance", "offered"), [(1, False), (2, True)])
async def test_the_bot_offers_lifts_of_the_entrance_of_the_flat_only(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    own_entrance: int,
    offered: bool,
) -> None:
    await _two_entrances(session, own.house_id)
    await _report(
        session,
        await _neighbour(session, own.house_id, "11", 2),
        own.house_id,
        2,
    )
    flat = await HousesRepo(session).get_flat(own.flat_id)
    assert flat is not None
    flat.entrance = own_entrance
    await session.flush()

    offer = await requests_service(session).neighbours(
        own.user_id,
        own.house_id,
        RequestCategory.ELEVATOR,
    )

    assert (offer is not None) is offered
