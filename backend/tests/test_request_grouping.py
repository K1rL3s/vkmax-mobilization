from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import Fixture, OrgHouseFlatUser, events_of, requests_service
from tests.test_requests import (
    _add_group,
    _age,
    _complain,
    _group_of_three,
    _neighbour,
)

from zheka.core.enums import (
    EventType,
    RequestCategory,
    RequestChannel,
    RequestGroupStatus,
    RequestStatus,
    ResidentRole,
)
from zheka.core.errors import InvalidRequest
from zheka.core.ids import FlatId, HouseId, UserId
from zheka.core.models import Request
from zheka.core.services.request_groups import (
    DEFAULT_GROUP_THRESHOLD,
    DEFAULT_GROUP_WINDOW_HOURS,
    complaint_sources,
)
from zheka.core.services.requests import RequestDraft
from zheka.infra.database.models import RequestGroup
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
