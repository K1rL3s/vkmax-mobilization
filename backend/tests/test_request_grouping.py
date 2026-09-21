import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser, make_config, make_notifications_service

from zheka.core.enums import (
    EventType,
    RequestCategory,
    RequestGroupStatus,
    RequestStatus,
    ResidentRole,
)
from zheka.core.ids import (
    FlatId,
    HouseId,
    MaxUserId,
    RequestGroupId,
    RequestId,
    UserId,
)
from zheka.core.models import Request
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.request_groups import (
    DEFAULT_GROUP_THRESHOLD,
    DEFAULT_GROUP_WINDOW_HOURS,
    GroupingService,
    complaint_sources,
    group_window_start,
    should_form_group,
)
from zheka.core.services.requests import RequestDraft, RequestsService
from zheka.infra.database.models import Event, Flat, RequestGroup, Resident, User
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.events import events_table
from zheka.infra.database.tables.requests import request_groups_table, requests_table
from zheka.infra.yandex import YandexClassifier

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


def _make_service(session: AsyncSession) -> RequestsService:
    return RequestsService(
        RequestsRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        UsersRepo(session),
        OrgsRepo(session),
        FilesService(make_config().files, "test-token"),
        GroupingService(RequestsRepo(session), EventsService(EventsRepo(session))),
        make_notifications_service(session),
        EventsService(EventsRepo(session)),
        YandexClassifier(make_config().yandex),
    )


async def _neighbour(
    session: AsyncSession,
    house_id: HouseId,
    number: str,
) -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name=f"Сосед {number}")
    flat = Flat(house_id=house_id, number=number)
    session.add_all([user, flat])
    await session.flush()
    session.add(
        Resident(
            user_id=user.id,
            house_id=house_id,
            flat_id=flat.id,
            role=ResidentRole.OWNER,
        ),
    )
    await session.flush()
    return UserId(user.id)


async def _complain(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    category: RequestCategory = RequestCategory.LEAK,
) -> Request:
    service = _make_service(session)
    card = await service.create(
        user_id,
        house_id,
        RequestDraft(category=category, description="Течет стояк"),
    )
    return card.request


async def _age(session: AsyncSession, request_id: RequestId, hours: int) -> None:
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(created_at=datetime.now(UTC) - timedelta(hours=hours))
    )
    await session.execute(stmt)
    await session.flush()


async def _groups(session: AsyncSession, house_id: HouseId) -> list[RequestGroup]:
    stmt = select(RequestGroup).where(request_groups_table.c.house_id == house_id)
    return list((await session.execute(stmt)).scalars().all())


async def _events(session: AsyncSession, type_: EventType) -> list[Event]:
    stmt = select(Event).where(events_table.c.type == type_)
    return list((await session.execute(stmt)).scalars().all())


def test_group_window_start_counts_back_from_now() -> None:
    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)

    assert group_window_start(now, 24) == datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def test_should_form_group_triggers_on_the_threshold_itself() -> None:
    assert should_form_group(DEFAULT_GROUP_THRESHOLD, DEFAULT_GROUP_THRESHOLD) is True
    assert should_form_group(DEFAULT_GROUP_THRESHOLD - 1, DEFAULT_GROUP_THRESHOLD) is (
        False
    )


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
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    second = await _neighbour(session, own.house_id, "2")
    third = await _neighbour(session, own.house_id, "3")

    first_request = await _complain(session, own.user_id, own.house_id)
    second_request = await _complain(session, second, own.house_id)
    third_request = await _complain(session, third, own.house_id)

    groups = await _groups(session, own.house_id)
    assert len(groups) == 1
    group_id = groups[0].id
    assert third_request.group_id == group_id
    # группа забирает и те заявки, что были поданы до нее
    assert first_request.group_id == group_id
    assert second_request.group_id == group_id
    formed = await _events(session, EventType.REQUEST_GROUP_FORMED)
    assert len(formed) == 1
    assert formed[0].payload["size"] == DEFAULT_GROUP_THRESHOLD


async def test_the_fourth_request_joins_the_group_instead_of_forming_a_second(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    for number in ("2", "3"):
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
        )
    await _complain(session, own.user_id, own.house_id)
    fourth = await _neighbour(session, own.house_id, "4")

    fourth_request = await _complain(session, fourth, own.house_id)

    groups = await _groups(session, own.house_id)
    assert len(groups) == 1
    assert fourth_request.group_id == groups[0].id
    joined = await _events(session, EventType.REQUEST_JOINED)
    assert len(joined) == 1
    assert joined[0].payload["group_size"] == DEFAULT_GROUP_THRESHOLD + 1


async def test_a_request_outside_the_window_starts_the_count_anew(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    second = await _neighbour(session, own.house_id, "2")
    stale = [
        RequestId((await _complain(session, own.user_id, own.house_id)).id),
        RequestId((await _complain(session, second, own.house_id)).id),
    ]
    for request_id in stale:
        await _age(session, request_id, DEFAULT_GROUP_WINDOW_HOURS + 1)
    third = await _neighbour(session, own.house_id, "3")

    await _complain(session, third, own.house_id)

    assert await _groups(session, own.house_id) == []


async def test_another_category_never_joins_the_group(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    second = await _neighbour(session, own.house_id, "2")
    third = await _neighbour(session, own.house_id, "3")
    await _complain(session, own.user_id, own.house_id)
    await _complain(session, second, own.house_id)

    elevator = await _complain(
        session,
        third,
        own.house_id,
        RequestCategory.ELEVATOR,
    )

    assert elevator.group_id is None
    assert await _groups(session, own.house_id) == []


async def test_a_group_of_another_house_is_not_joined(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    for number in ("2", "3"):
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
        )
    await _complain(session, own.user_id, own.house_id)

    foreign = await _complain(session, other.user_id, other.house_id)

    assert foreign.group_id is None
    assert len(await _groups(session, own.house_id)) == 1


async def test_similar_counts_neighbours_without_the_asking_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
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
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    for number in ("2", "3", "4"):
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
        )
    service = _make_service(session)

    similar = await service.similar(own.user_id, own.house_id, RequestCategory.LEAK)

    assert similar.group_id is not None
    assert similar.flats_count == DEFAULT_GROUP_THRESHOLD


async def test_a_closed_group_is_not_joined(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    for number in ("2", "3"):
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
        )
    await _complain(session, own.user_id, own.house_id)
    groups = await _groups(session, own.house_id)
    closed_id = RequestGroupId(groups[0].id)
    await RequestsRepo(session).set_group_status(groups[0], RequestGroupStatus.CLOSED)
    fourth = await _neighbour(session, own.house_id, "4")

    fourth_request = await _complain(session, fourth, own.house_id)

    # закрытая группа - закрытый наряд работ: жалоба в него не падает, а
    # собирает новую группу, потому что проблема все еще открыта
    assert fourth_request.group_id is not None
    assert fourth_request.group_id != closed_id


async def test_three_complaints_from_one_resident_do_not_form_a_group(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)

    for _ in range(DEFAULT_GROUP_THRESHOLD):
        await _complain(session, own.user_id, own.house_id)

    # склейка считает жалобщиков: три жалобы одного жителя - одна проблема,
    # а не коллективная
    assert await _groups(session, own.house_id) == []


async def test_a_formed_group_does_not_swallow_another_category(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    for number in ("2", "3"):
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
        )
    await _complain(session, own.user_id, own.house_id)
    assert len(await _groups(session, own.house_id)) == 1
    fourth = await _neighbour(session, own.house_id, "4")

    elevator = await _complain(
        session,
        fourth,
        own.house_id,
        RequestCategory.ELEVATOR,
    )

    # группа собрана по протечке, лифт в нее не падает
    assert elevator.group_id is None
