from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser
from tests.test_requests import (
    _age,
    _complain,
    _events,
    _group_of_three,
    _make_service,
    _neighbour,
)

from zheka.core.enums import (
    EventType,
    RequestCategory,
    RequestGroupStatus,
    RequestStatus,
    ResidentRole,
)
from zheka.core.ids import FlatId, HouseId, UserId
from zheka.core.models import Request
from zheka.core.services.request_groups import (
    DEFAULT_GROUP_THRESHOLD,
    DEFAULT_GROUP_WINDOW_HOURS,
    complaint_sources,
)
from zheka.infra.database.models import RequestGroup
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.tables.requests import request_groups_table

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


async def _groups(session: AsyncSession, house_id: HouseId) -> list[RequestGroup]:
    stmt = select(RequestGroup).where(request_groups_table.c.house_id == house_id)
    return list((await session.execute(stmt)).scalars().all())


def test_complaint_sources_count_complainants_and_not_requests() -> None:
    requests = [
        Request(
            house_id=HouseId(1),
            flat_id=FlatId(7),
            category=RequestCategory.LEAK,
            description="раз",
            status=RequestStatus.NEW,
            channel="miniapp",  # type: ignore[arg-type]
        ),
        Request(
            house_id=HouseId(1),
            flat_id=FlatId(7),
            category=RequestCategory.LEAK,
            description="два",
            status=RequestStatus.NEW,
            channel="miniapp",  # type: ignore[arg-type]
        ),
        Request(
            house_id=HouseId(1),
            flat_id=None,
            author_user_id=UserId(42),
            category=RequestCategory.LEAK,
            description="три",
            status=RequestStatus.NEW,
            channel="miniapp",  # type: ignore[arg-type]
        ),
    ]

    # две жалобы из одной квартиры - одна протечка, а заявка про общее
    # имущество считается по автору
    assert complaint_sources(requests) == {("flat", 7), ("user", 42)}


async def test_three_flats_in_the_window_form_exactly_one_group(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)

    members, group_id = await _group_of_three(session, own)

    assert [group.id for group in await _groups(session, own.house_id)] == [group_id]
    # группа забирает и те заявки, что были поданы до нее
    assert [member.group_id for member in members] == [group_id] * 3
    formed = await _events(session, EventType.REQUEST_GROUP_FORMED)
    assert len(formed) == 1
    assert formed[0].payload["size"] == DEFAULT_GROUP_THRESHOLD


async def test_the_fourth_request_joins_the_group_instead_of_forming_a_second(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    _, group_id = await _group_of_three(session, own)

    fourth_request = await _complain(session, own.user_id, own.house_id)

    assert len(await _groups(session, own.house_id)) == 1
    assert fourth_request.group_id == group_id
    joined = await _events(session, EventType.REQUEST_JOINED)
    assert len(joined) == 1
    assert joined[0].payload["group_size"] == DEFAULT_GROUP_THRESHOLD + 1


async def test_a_request_outside_the_window_starts_the_count_anew(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
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


async def test_another_category_never_joins_the_group(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    second = await _neighbour(session, own.house_id, "2")
    third = await _neighbour(session, own.house_id, "3")
    await _complain(session, own.user_id, own.house_id)
    await _complain(session, second, own.house_id)

    elevator = await _complain(session, third, own.house_id, RequestCategory.ELEVATOR)

    assert elevator.group_id is None
    assert await _groups(session, own.house_id) == []


async def test_a_group_of_another_house_is_not_joined(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _group_of_three(session, own)

    foreign = await _complain(session, other.user_id, other.house_id)

    assert foreign.group_id is None
    assert len(await _groups(session, own.house_id)) == 1


async def test_similar_counts_neighbours_without_the_asking_resident(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    second = await _neighbour(session, own.house_id, "2")
    await _complain(session, own.user_id, own.house_id)
    await _complain(session, second, own.house_id)
    service = _make_service(session)

    similar = await service.similar(own.user_id, own.house_id, RequestCategory.LEAK)

    # пожаловался сосед, а сам спрашивающий в «N соседей» не входит
    assert similar.flats_count == 1
    assert similar.group_id is None


async def test_similar_offers_the_group_once_it_exists(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _group_of_three(session, own)
    service = _make_service(session)

    similar = await service.similar(own.user_id, own.house_id, RequestCategory.LEAK)

    assert similar.group_id is not None
    assert similar.flats_count == DEFAULT_GROUP_THRESHOLD


async def test_a_closed_group_is_not_joined(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    _, closed_id = await _group_of_three(session, own)
    [group] = await _groups(session, own.house_id)
    await RequestsRepo(session).set_group_status(group, RequestGroupStatus.CLOSED)

    fourth_request = await _complain(session, own.user_id, own.house_id)

    # закрытая группа - закрытый наряд работ: жалоба в него не падает, а
    # собирает новую группу, потому что проблема все еще открыта
    assert fourth_request.group_id is not None
    assert fourth_request.group_id != closed_id


async def test_three_complaints_from_one_resident_do_not_form_a_group(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)

    for _ in range(DEFAULT_GROUP_THRESHOLD):
        await _complain(session, own.user_id, own.house_id)

    # склейка считает жалобщиков: три жалобы одного жителя - одна проблема,
    # а не коллективная
    assert await _groups(session, own.house_id) == []


async def test_a_formed_group_does_not_swallow_another_category(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _group_of_three(session, own)

    elevator = await _complain(
        session, own.user_id, own.house_id, RequestCategory.ELEVATOR
    )

    # группа собрана по протечке, лифт в нее не падает
    assert elevator.group_id is None
