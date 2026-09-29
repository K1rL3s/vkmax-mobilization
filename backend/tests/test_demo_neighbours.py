import secrets
from datetime import UTC, datetime, timedelta

import pytest
from maxo.utils.webapp import WebAppChat, WebAppInitData, WebAppUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    add_resident,
    add_user,
    admin_requests_service,
    events_of,
    make_config,
    photo_name,
    requests_service,
)
from tests.test_requests import _age

from zheka.api.dependencies.current_account import CurrentAccount
from zheka.api.dependencies.current_user import API_CHECKER
from zheka.api.routes.requests import add_demo_neighbours
from zheka.api.schemas.requests import RequestCard
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import (
    ChatCardKind,
    EventType,
    OrgRole,
    RequestCategory,
    RequestChannel,
    RequestStatus,
    ResidentRole,
    ResidentStatus,
)
from zheka.core.errors import EntityNotFound, NotEnoughRights
from zheka.core.ids import (
    API_CHECKER_MAX_USER_ID,
    DEMO_TENANT_MAX_ID_BASE,
    HouseId,
    MaxUserId,
    OrgId,
    UserId,
)
from zheka.core.models import Flat, OrgMember, OrgSettings, Request, User
from zheka.core.services.files import FilesService
from zheka.core.services.requests import DEMO_NEIGHBOURS, RequestDraft
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.tables.requests import requests_table

WINDOW_HOURS = 6


async def _demo(session: AsyncSession, org_id: OrgId) -> None:
    org = await OrgsRepo(session).get(org_id)
    assert org is not None
    org.is_demo = True
    session.add(
        OrgSettings(
            org_id=org_id,
            group_threshold=10,
            group_window_hours=WINDOW_HOURS,
        ),
    )
    await session.flush()


async def _model(
    session: AsyncSession,
    house_id: HouseId,
    number: str,
    *,
    max_user_id: int | None = None,
    status: ResidentStatus = ResidentStatus.ACTIVE,
    flat: Flat | None = None,
) -> UserId:
    user = User(
        max_user_id=MaxUserId(
            -(secrets.randbits(40) + 1) if max_user_id is None else max_user_id,
        ),
        name=f"Модельный {number}",
    )
    if flat is None:
        flat = Flat(house_id=house_id, number=number)
    session.add_all([user, flat])
    await session.flush()
    await add_resident(session, user.id, house_id, flat.id, status=status)
    return user.id


async def _file(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    category: RequestCategory = RequestCategory.ELEVATOR,
) -> Request:
    card = await requests_service(session).create(
        user_id,
        house_id,
        RequestDraft(category=category, description="Лифт стоит"),
    )
    return card.request


async def _neighbour_requests(session: AsyncSession, request: Request) -> list[Request]:
    stmt = (
        select(Request)
        .where(
            requests_table.c.group_id == request.group_id,
            requests_table.c.id != request.id,
        )
        .order_by(requests_table.c.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def test_the_button_groups_the_request_with_four_model_neighbours(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    await _demo(session, own.org_id)
    staff = await add_user(session, "Сотрудник")
    session.add(OrgMember(org_id=own.org_id, user_id=staff, role=OrgRole.EMPLOYEE))
    models = [
        await _model(session, own.house_id, str(number)) for number in range(10, 16)
    ]
    request = await _file(session, own.user_id, own.house_id)
    service = requests_service(session, publisher)
    assert (await service.get_card(own.user_id, request.id)).can_demo_neighbours

    card = await service.demo_neighbours(own.user_id, request.id, datetime.now(UTC))

    assert card.group_size == 1 + DEMO_NEIGHBOURS
    assert card.can_demo_neighbours is False
    neighbours = await _neighbour_requests(session, request)
    assert len(neighbours) == DEMO_NEIGHBOURS
    assert {item.author_user_id for item in neighbours} <= set(models)
    assert len({item.flat_id for item in neighbours}) == DEMO_NEIGHBOURS
    for item in neighbours:
        assert item.category is RequestCategory.ELEVATOR
        assert item.channel is RequestChannel.MINIAPP
        assert item.description == "Та же проблема: лифт"
        assert item.is_staff_author is False
    assert len(await events_of(session, EventType.REQUEST_CREATED)) == 1
    [formed] = await events_of(session, EventType.REQUEST_GROUP_FORMED)
    assert formed.payload["size"] == 1 + DEMO_NEIGHBOURS
    await publisher.flush()
    group_syncs = [
        sync
        for sync in broker.enqueued(TaskName.SYNC_CHAT_CARD)
        if sync["kind"] == ChatCardKind.GROUP
    ]
    assert group_syncs == [
        {"kind": ChatCardKind.GROUP, "ref_id": request.group_id, "post": True},
    ]
    assert broker.enqueued(TaskName.BROADCAST_TO_USERS) == []
    assert broker.enqueued(TaskName.SEND_TO_USER) == []


async def test_neighbours_never_warn_staff_about_their_deadlines(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    await _model(session, own.house_id, "10")
    request = await _file(session, own.user_id, own.house_id)
    service = requests_service(session)
    await service.demo_neighbours(own.user_id, request.id, datetime.now(UTC))

    late = request.deadline_at + timedelta(minutes=1)

    assert await service.watch_deadlines(late) == 1


async def test_one_neighbour_is_enough_whatever_the_org_threshold(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    await _model(session, own.house_id, "10")
    request = await _file(session, own.user_id, own.house_id)

    card = await requests_service(session).demo_neighbours(
        own.user_id,
        request.id,
        datetime.now(UTC),
    )

    assert card.group_size == 2


async def _refused(
    session: AsyncSession,
    user_id: UserId,
    request: Request,
) -> None:
    service = requests_service(session)
    if request.author_user_id == user_id:
        card = await service.get_card(user_id, request.id)
        assert card.can_demo_neighbours is False
    with pytest.raises(EntityNotFound):
        await service.demo_neighbours(user_id, request.id, datetime.now(UTC))


async def test_the_button_is_only_in_a_demo_org(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _model(session, own.house_id, "10")
    request = await _file(session, own.user_id, own.house_id)

    await _refused(session, own.user_id, request)


async def test_the_button_is_only_for_the_author(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    await _model(session, own.house_id, "10")
    stranger = await add_user(session, "Проверяющий")
    await add_resident(session, stranger, own.house_id, None)
    request = await _file(session, own.user_id, own.house_id)

    await _refused(session, stranger, request)


async def test_the_staff_card_has_no_button(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    await _model(session, own.house_id, "10")
    request = await _file(session, own.user_id, own.house_id)

    staff_card = await admin_requests_service(session).card(own.org_id, request.id)

    assert staff_card.card.can_demo_neighbours is False


async def test_a_grouped_request_gets_no_second_round(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    for number in range(10, 16):
        await _model(session, own.house_id, str(number))
    request = await _file(session, own.user_id, own.house_id)
    await requests_service(session).demo_neighbours(
        own.user_id,
        request.id,
        datetime.now(UTC),
    )

    await _refused(session, own.user_id, request)


async def test_a_closed_request_gets_no_neighbours(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    await _model(session, own.house_id, "10")
    request = await _file(session, own.user_id, own.house_id)
    request.status = RequestStatus.ON_REVIEW
    await session.flush()

    await _refused(session, own.user_id, request)


async def test_a_request_past_the_org_window_gets_no_neighbours(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    await _model(session, own.house_id, "10")
    request = await _file(session, own.user_id, own.house_id)
    await _age(session, request.id, WINDOW_HOURS + 1)
    await session.refresh(request)

    await _refused(session, own.user_id, request)


async def test_real_users_are_never_neighbours(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    real = await add_user(session, "Проверяющий")
    flat = Flat(house_id=own.house_id, number="10")
    session.add(flat)
    await session.flush()
    await add_resident(session, real, own.house_id, flat.id)
    await _model(session, own.house_id, "11", max_user_id=API_CHECKER_MAX_USER_ID)
    request = await _file(session, own.user_id, own.house_id)

    await _refused(session, own.user_id, request)


async def test_a_blocked_model_resident_is_not_a_neighbour(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    await _model(session, own.house_id, "10", status=ResidentStatus.BLOCKED)
    request = await _file(session, own.user_id, own.house_id)

    await _refused(session, own.user_id, request)


async def test_a_flat_that_already_complained_is_not_a_new_neighbour(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    model = await _model(session, own.house_id, "10")
    await _file(session, model, own.house_id)
    request = await _file(session, own.user_id, own.house_id)

    await _refused(session, own.user_id, request)


async def test_a_flat_that_already_complained_through_its_flat_is_not_a_neighbour(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    flat = Flat(house_id=own.house_id, number="10")
    await _model(session, own.house_id, "10", flat=flat)
    other = await _model(session, own.house_id, "10", flat=flat)
    card = await requests_service(session).create(
        other,
        own.house_id,
        RequestDraft(
            category=RequestCategory.ELEVATOR,
            description="Лифт стоит",
            flat_id=flat.id,
        ),
    )
    assert card.request.flat_id == flat.id
    request = await _file(session, own.user_id, own.house_id)

    await _refused(session, own.user_id, request)


async def test_a_complaint_of_another_category_leaves_the_flat_free(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    model = await _model(session, own.house_id, "10")
    await _file(session, model, own.house_id, RequestCategory.GARBAGE)
    request = await _file(session, own.user_id, own.house_id)

    card = await requests_service(session).demo_neighbours(
        own.user_id,
        request.id,
        datetime.now(UTC),
    )

    assert card.group_size == 2


async def test_two_model_residents_of_one_flat_are_one_neighbour(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    flat = Flat(house_id=own.house_id, number="10")
    await _model(session, own.house_id, "10", flat=flat)
    await _model(session, own.house_id, "10", flat=flat)
    request = await _file(session, own.user_id, own.house_id)

    await requests_service(session).demo_neighbours(
        own.user_id,
        request.id,
        datetime.now(UTC),
    )

    assert len(await _neighbour_requests(session, request)) == 1


async def test_model_residents_of_another_house_stay_home(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _demo(session, own.org_id)
    await _model(session, other.house_id, "10")
    request = await _file(session, own.user_id, own.house_id)

    await _refused(session, own.user_id, request)


async def test_a_model_resident_without_a_flat_is_not_a_neighbour(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    model = User(max_user_id=MaxUserId(-(secrets.randbits(40) + 1)), name="Модельный")
    session.add(model)
    await session.flush()
    await add_resident(session, model.id, own.house_id, None)
    request = await _file(session, own.user_id, own.house_id)

    await _refused(session, own.user_id, request)


@pytest.mark.parametrize("stale", [False, True])
async def test_a_closed_or_stale_complaint_leaves_the_flat_free(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    stale: bool,
) -> None:
    await _demo(session, own.org_id)
    model = await _model(session, own.house_id, "10")
    complaint = await _file(session, model, own.house_id)
    if stale:
        await _age(session, complaint.id, WINDOW_HOURS + 1)
    else:
        complaint.status = RequestStatus.DONE
        await session.flush()
    request = await _file(session, own.user_id, own.house_id)

    card = await requests_service(session).demo_neighbours(
        own.user_id,
        request.id,
        datetime.now(UTC),
    )

    assert card.group_size == 2


async def test_neighbours_of_a_repeat_join_the_open_group_with_it(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    for number in range(10, 18):
        await _model(session, own.house_id, str(number))
    first = await _file(session, own.user_id, own.house_id)
    service = requests_service(session)
    await service.demo_neighbours(own.user_id, first.id, datetime.now(UTC))
    assert first.group_id is not None
    await admin_requests_service(session).change_group_status(
        own.org_id,
        first.group_id,
        RequestStatus.ON_REVIEW,
        None,
        own.user_id,
    )
    repeat = await service.reject(
        own.user_id,
        first.id,
        "Лифт снова стоит",
        [photo_name()],
        RequestChannel.MINIAPP,
    )
    assert repeat.can_demo_neighbours

    card = await service.demo_neighbours(
        own.user_id,
        repeat.request.id,
        datetime.now(UTC),
    )

    assert card.request.group_id == first.group_id
    stmt = select(Request).where(
        requests_table.c.house_id == own.house_id,
        requests_table.c.group_id.is_(None),
    )
    assert (await session.execute(stmt)).scalars().all() == []


async def test_a_flat_whose_complaint_is_on_review_is_not_a_new_neighbour(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    model = await _model(session, own.house_id, "10")
    complaint = await _file(session, model, own.house_id)
    complaint.status = RequestStatus.ON_REVIEW
    await session.flush()
    request = await _file(session, own.user_id, own.house_id)

    await _refused(session, own.user_id, request)


async def test_a_reviewers_demo_tenant_is_never_a_neighbour(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    reviewer = await add_user(session, "Другой проверяющий")
    await _model(
        session,
        own.house_id,
        "Д1",
        max_user_id=DEMO_TENANT_MAX_ID_BASE - reviewer,
    )
    request = await _file(session, own.user_id, own.house_id)

    await _refused(session, own.user_id, request)


@pytest.mark.parametrize(
    ("user", "gathered"),
    [
        (API_CHECKER, False),
        (
            WebAppInitData(
                chat=WebAppChat(id=7, type="DIALOG"),
                user=WebAppUser(id=7, first_name="Житель"),
                hash="",
            ),
            True,
        ),
    ],
    ids=["checker", "resident"],
)
async def test_the_checker_gathers_no_neighbours_for_its_requests(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    user: WebAppInitData,
    gathered: bool,
) -> None:
    await _demo(session, own.org_id)
    await _model(session, own.house_id, "10")
    request = await _file(session, own.user_id, own.house_id)

    async def gather() -> RequestCard:
        return await add_demo_neighbours(
            request.id,
            user,
            CurrentAccount(user_id=own.user_id, consent_at=datetime.now(UTC)),
            requests_service(session),
            FilesService(make_config().files, "test-token"),
        )

    if gathered:
        card = await gather()
        assert card.group_size == 2
    else:
        with pytest.raises(NotEnoughRights):
            await gather()
        assert request.group_id is None
