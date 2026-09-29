from collections.abc import Callable

import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from maxo.utils.webapp import WebAppChat, WebAppInitData, WebAppUser
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    admin_requests_service,
    category_executors_service,
    events_of,
    make_config,
    photo_name,
    requests_service,
)
from tests.test_orgs import make_orgs_service
from tests.test_requests import (
    _age,
    _complain,
    _group_of_three,
    _member,
    _neighbour,
)

from zheka.api.dependencies.current_org import CurrentOrg, require_admin_org
from zheka.api.dependencies.current_user import API_CHECKER
from zheka.api.routes.admin.orgs import router as admin_orgs_router
from zheka.api.routes.admin.requests import change_request_status
from zheka.api.schemas.requests import AdminRequestCard, ChangeRequestStatusRequest
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core import texts
from zheka.core.enums import (
    CATEGORY_RULES,
    EventType,
    OrgRole,
    RequestActorRole,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestGroupStatus,
    RequestStatus,
    ResidentRole,
    ResidentStatus,
)
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import RequestId, ResidentId, UserId
from zheka.core.services.admin_requests import RESIDENT_BLOCKED, PhoneRequestDraft
from zheka.core.services.files import FilesService
from zheka.core.services.requests import RequestDraft
from zheka.infra.database.models import Flat
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestFilters
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.tables.requests import (
    request_status_log_table,
    requests_table,
)

NO_FILTERS = RequestFilters()
_STAFF_INIT_DATA = WebAppInitData(
    chat=WebAppChat(id=7, type="DIALOG"),
    user=WebAppUser(id=7, first_name="Сотрудник"),
    hash="",
)
TO_REVIEW = (RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS, RequestStatus.ON_REVIEW)


async def _logs(session: AsyncSession, request_id: RequestId) -> list[RequestStatus]:
    stmt = (
        select(request_status_log_table.c.to_status)
        .where(request_status_log_table.c.request_id == request_id)
        .order_by(request_status_log_table.c.id)
    )
    return list((await session.execute(stmt)).scalars().all())


def _phone_draft(
    own: OrgHouseFlatUser,
    description: str = "Течет",
    **fields: object,
) -> PhoneRequestDraft:
    return PhoneRequestDraft(
        house_id=own.house_id,
        category=RequestCategory.LEAK,
        description=description,
        **fields,  # type: ignore[arg-type]
    )


async def test_inbox_never_shows_a_request_of_another_organization(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    foreign = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    mine = await _complain(session, own.user_id, own.house_id)
    await _complain(session, foreign.user_id, foreign.house_id)

    service = admin_requests_service(session)
    rows, total = await service.inbox(own.org_id, NO_FILTERS, 20, 0)

    assert total == 1
    assert [row.request.id for row in rows] == [mine.id]


async def test_a_request_of_another_organization_is_not_found_by_id(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    foreign = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    alien = await _complain(session, foreign.user_id, foreign.house_id)

    with pytest.raises(EntityNotFound):
        await admin_requests_service(session).card(own.org_id, alien.id)


async def test_overdue_requests_come_first_and_can_be_filtered(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    fresh = await _complain(session, own.user_id, own.house_id)
    late = await _complain(session, own.user_id, own.house_id)
    done = await _complain(session, own.user_id, own.house_id)
    review = await _complain(session, own.user_id, own.house_id)
    normative = CATEGORY_RULES[RequestCategory.LEAK].fix_hours
    await _age(session, late.id, normative + 1)
    await _age(session, done.id, normative + 2)
    await _age(session, review.id, normative + 3)
    done.status = RequestStatus.DONE
    review.status = RequestStatus.ON_REVIEW
    await session.flush()
    service = admin_requests_service(session)

    rows, _ = await service.inbox(own.org_id, NO_FILTERS, 20, 0)
    second, _ = await service.inbox(own.org_id, NO_FILTERS, 1, 1)
    only_overdue, total = await service.inbox(
        own.org_id,
        RequestFilters(overdue=True),
        20,
        0,
    )

    assert [row.request.id for row in rows] == [late.id, fresh.id, done.id, review.id]
    assert [row.request.id for row in second] == [fresh.id]
    assert total == 1
    assert [row.request.id for row in only_overdue] == [late.id]


async def test_grouped_collapses_a_group_into_one_row(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    members, _ = await _group_of_three(session, own)
    service = admin_requests_service(session)

    plain, plain_total = await service.inbox(own.org_id, NO_FILTERS, 20, 0)
    collapsed, collapsed_total = await service.inbox(
        own.org_id,
        RequestFilters(grouped=True),
        20,
        0,
    )

    assert plain_total == 3
    assert len(plain) == 3
    assert collapsed_total == 1
    assert [row.request.id for row in collapsed] == [members[0].id]
    assert collapsed[0].group_size == 3


async def test_change_status_writes_the_log_the_stamp_and_the_event(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)
    request_id = request.id

    card = await admin_requests_service(session).change_status(
        own.org_id,
        request_id,
        RequestStatus.ACCEPTED,
        "Приняли, выехали",
        staff,
    )

    assert card.card.request.status is RequestStatus.ACCEPTED
    assert card.card.request.accepted_at is not None
    assert await _logs(session, request_id) == [
        RequestStatus.NEW,
        RequestStatus.ACCEPTED,
    ]
    assert [message.message.text for message in card.card.messages] == [
        "Приняли, выехали",
    ]
    events = await events_of(session, EventType.REQUEST_STATUS_CHANGED)
    assert events[0].payload == {
        "request_id": request_id,
        "from": RequestStatus.NEW.value,
        "to": RequestStatus.ACCEPTED.value,
        "by_role": RequestActorRole.STAFF.value,
    }


async def test_phone_request_carries_the_caller_and_no_author(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = admin_requests_service(session, publisher)

    card = await service.create_phone(
        own.org_id,
        _phone_draft(own, caller_name="Мария Ивановна", caller_phone="+70000000000"),
        staff,
    )

    request = card.card.request
    assert request.channel is RequestChannel.PHONE
    assert request.is_staff_author is True
    assert request.author_user_id is None
    assert request.flat_id is None
    assert request.caller_name == "Мария Ивановна"
    assert request.caller_phone == "+70000000000"
    assert await _logs(session, request.id) == [RequestStatus.NEW]
    await service.reply(own.org_id, request.id, "Мастер придет завтра", staff)
    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_TO_USER) == []


async def test_phone_request_refuses_without_a_flat_or_full_caller_details(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = admin_requests_service(session)

    for fields in ({}, {"caller_name": "Мария"}, {"caller_phone": "+70000000000"}):
        with pytest.raises(InvalidRequest):
            await service.create_phone(own.org_id, _phone_draft(own, **fields), staff)
    with pytest.raises(InvalidRequest):
        await service.create_phone(
            own.org_id,
            _phone_draft(own, "   ", flat_id=own.flat_id),
            staff,
        )


async def test_phone_request_refuses_a_house_or_flat_of_another_organization(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    foreign = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = admin_requests_service(session)

    for house in (foreign, own):
        with pytest.raises(EntityNotFound):
            await service.create_phone(
                own.org_id,
                _phone_draft(house, flat_id=foreign.flat_id),
                staff,
            )


async def test_reply_writes_a_message_from_the_management(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)

    card = await admin_requests_service(session).reply(
        own.org_id,
        request.id,
        "  Мастер придет завтра  ",
        staff,
    )

    assert [message.message.text for message in card.card.messages] == [
        "Мастер придет завтра",
    ]
    assert card.card.messages[0].message.author_role == RequestActorRole.STAFF
    assert card.card.messages[0].author is not None


async def test_reply_refuses_an_empty_text(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)

    service = admin_requests_service(session)

    with pytest.raises(InvalidRequest):
        await service.reply(own.org_id, request.id, "   ", staff)


async def test_assign_takes_an_executor_leaves_the_status_and_opens_his_card(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)

    card = await admin_requests_service(session, publisher).assign(
        own.org_id,
        request.id,
        executor,
        staff,
    )

    assert card.card.request.executor_user_id == executor
    assert card.card.request.status is RequestStatus.NEW
    assigned = await events_of(session, EventType.REQUEST_ASSIGNED)
    assert [(event.user_id, event.payload) for event in assigned] == [
        (staff, {"request_id": request.id, "executor_user_id": executor}),
    ]
    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_EXECUTOR_CARD) == [
        {"request_id": request.id, "user_id": None},
    ]


async def test_assign_refuses_a_member_who_is_not_an_executor(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)

    service = admin_requests_service(session)

    with pytest.raises(InvalidRequest):
        await service.assign(own.org_id, request.id, staff, staff)


async def test_assign_refuses_an_executor_of_another_organization(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    foreign = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    alien = await _member(session, foreign.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)

    service = admin_requests_service(session)

    with pytest.raises(EntityNotFound):
        await service.assign(own.org_id, request.id, alien, staff)


async def test_executors_are_listed_with_their_load(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)
    service = admin_requests_service(session)
    await service.assign(own.org_id, request.id, executor, staff)

    views = await service.executors(own.org_id)

    assert [view.user.id for view in views] == [executor]
    assert views[0].active_requests == 1


async def test_a_group_of_another_organization_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    foreign = await make_org_house_flat_user()
    _, group_id = await _group_of_three(session, foreign)

    with pytest.raises(EntityNotFound):
        await admin_requests_service(session).group_card(own.org_id, group_id)


async def test_a_group_already_in_the_target_status_is_refused(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    _, group_id = await _group_of_three(session, own)
    service = admin_requests_service(session)
    await service.change_group_status(
        own.org_id,
        group_id,
        RequestStatus.ACCEPTED,
        None,
        staff,
    )

    with pytest.raises(InvalidState):
        await service.change_group_status(
            own.org_id,
            group_id,
            RequestStatus.ACCEPTED,
            None,
            staff,
        )


async def test_staff_closes_a_group_of_phone_requests_and_its_row(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = admin_requests_service(session)
    flats = [own.flat_id]
    for number in ("2", "3"):
        flat = Flat(house_id=own.house_id, number=number)
        session.add(flat)
        await session.flush()
        flats.append(flat.id)
    cards = [
        await service.create_phone(own.org_id, _phone_draft(own, flat_id=flat), staff)
        for flat in flats
    ]
    group_id = cards[-1].card.request.group_id
    assert group_id is not None
    for target in TO_REVIEW:
        await service.change_group_status(own.org_id, group_id, target, None, staff)

    card = await service.change_group_status(
        own.org_id,
        group_id,
        RequestStatus.DONE,
        None,
        staff,
    )

    assert card.group.status is RequestGroupStatus.CLOSED
    assert all(row.request.status is RequestStatus.DONE for row in card.rows)


async def test_group_status_carries_a_late_joiner_through_two_steps(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    members, group_id = await _group_of_three(session, own)
    service = admin_requests_service(session)
    for target in (RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS):
        await service.change_group_status(own.org_id, group_id, target, None, staff)

    latecomer = await _complain(
        session,
        await _neighbour(session, own.house_id, "4"),
        own.house_id,
    )
    assert latecomer.group_id == group_id
    assert latecomer.status is RequestStatus.NEW

    card = await service.change_group_status(
        own.org_id,
        group_id,
        RequestStatus.IN_PROGRESS,
        "Работаем",
        staff,
    )

    assert card.flats_count == 4
    assert len(card.rows) == 4
    assert all(row.request.status is RequestStatus.IN_PROGRESS for row in card.rows)
    for member in [*members, latecomer]:
        assert await _logs(session, member.id) == [
            RequestStatus.NEW,
            RequestStatus.ACCEPTED,
            RequestStatus.IN_PROGRESS,
        ]
    latecomer_card = await service.card(own.org_id, latecomer.id)
    assert [message.message.text for message in latecomer_card.card.messages] == [
        "Работаем",
    ]


async def test_group_status_refuses_a_member_ahead_of_the_target(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    members, group_id = await _group_of_three(session, own)
    service = admin_requests_service(session)
    ahead = members[0].id
    for target in (RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS):
        await service.change_status(own.org_id, ahead, target, None, staff)

    with pytest.raises(InvalidState):
        await service.change_group_status(
            own.org_id,
            group_id,
            RequestStatus.ACCEPTED,
            None,
            staff,
        )

    for member in members[1:]:
        assert await _logs(session, member.id) == [RequestStatus.NEW]


async def _assigned(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> tuple[RequestId, UserId]:
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)
    request_id = request.id
    service = admin_requests_service(session)
    await service.assign(own.org_id, request_id, executor, own.user_id)
    return request_id, executor


async def _in_progress(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> tuple[RequestId, UserId]:
    request_id, executor = await _assigned(session, own)
    service = admin_requests_service(session)
    await service.executor_advance(executor, request_id, RequestStatus.ACCEPTED, [])
    await service.executor_advance(executor, request_id, RequestStatus.IN_PROGRESS, [])
    return request_id, executor


async def test_the_executor_accepts_a_new_request_assigned_to_him(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id, executor = await _assigned(session, own)

    await admin_requests_service(session).executor_advance(
        executor,
        request_id,
        RequestStatus.ACCEPTED,
        [],
    )

    stmt = select(request_status_log_table).where(
        request_status_log_table.c.request_id == request_id,
        request_status_log_table.c.to_status == RequestStatus.ACCEPTED,
    )
    log = (await session.execute(stmt)).one()
    assert log.by_role == RequestActorRole.EXECUTOR
    assert log.by_user_id == executor
    events = await events_of(session, EventType.EXECUTOR_STATUS_CHANGED)
    assert [event.payload for event in events] == [
        {"request_id": request_id, "to": RequestStatus.ACCEPTED.value},
    ]


async def test_ready_without_a_result_photo_is_refused_and_writes_nothing(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id, executor = await _in_progress(session, own)

    with pytest.raises(InvalidState, match="фото результата"):
        await admin_requests_service(session).executor_advance(
            executor,
            request_id,
            RequestStatus.ON_REVIEW,
            [],
        )

    assert (await _logs(session, request_id))[-1] is RequestStatus.IN_PROGRESS


async def test_ready_with_a_result_photo_opens_the_review_card(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    request_id, executor = await _in_progress(session, own)
    name = photo_name()

    await admin_requests_service(session, publisher).executor_advance(
        executor,
        request_id,
        RequestStatus.ON_REVIEW,
        [name],
    )

    card = await admin_requests_service(session).executor_card(executor, request_id)
    assert card is not None
    assert card.request.status is RequestStatus.ON_REVIEW
    assert [photo.path for photo in card.result_photos] == [name]
    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_REVIEW_CARD) == [{"request_id": request_id}]
    assert broker.enqueued(TaskName.SEND_TO_USER) == []


async def test_a_refused_move_attaches_no_result_photo(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id, executor = await _in_progress(session, own)
    service = admin_requests_service(session)
    await service.executor_advance(
        executor,
        request_id,
        RequestStatus.ON_REVIEW,
        [photo_name()],
    )

    with pytest.raises(InvalidState):
        await service.executor_advance(
            executor,
            request_id,
            RequestStatus.ON_REVIEW,
            [photo_name()],
        )

    card = await service.executor_card(executor, request_id)
    assert card is not None
    assert len(card.result_photos) == 1


@pytest.mark.parametrize("loss", ["another_executor", "removed", "demoted"])
async def test_only_the_assigned_executor_of_the_org_can_advance(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    loss: str,
) -> None:
    request_id, executor = await _assigned(session, own)
    orgs_repo = OrgsRepo(session)
    member = await orgs_repo.get_member(own.org_id, executor)
    assert member is not None
    if loss == "another_executor":
        executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    elif loss == "removed":
        await orgs_repo.remove_member(member)
    else:
        await orgs_repo.set_member_role(member, OrgRole.EMPLOYEE)

    with pytest.raises(NotEnoughRights):
        await admin_requests_service(session).executor_advance(
            executor,
            request_id,
            RequestStatus.ACCEPTED,
            [],
        )
    assert (
        await admin_requests_service(session).executor_card(executor, request_id)
        is None
    )


async def _resident_id(session: AsyncSession, own: OrgHouseFlatUser) -> ResidentId:
    resident = await ResidentsRepo(session).get_for_house(own.user_id, own.house_id)
    assert resident is not None
    return resident.id


async def test_a_phone_request_for_a_resident_runs_the_ordinary_road(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = admin_requests_service(session, publisher)

    card = await service.create_phone(
        own.org_id,
        _phone_draft(own, resident_id=await _resident_id(session, own)),
        staff,
    )
    request = card.card.request
    request_id = request.id
    assert request.channel is RequestChannel.PHONE
    assert request.author_user_id == own.user_id
    assert request.flat_id == own.flat_id
    assert request.is_staff_author is False

    for target in TO_REVIEW:
        await service.change_status(own.org_id, request_id, target, None, staff)
    with pytest.raises(InvalidState):
        await service.change_status(
            own.org_id,
            request_id,
            RequestStatus.DONE,
            None,
            staff,
        )
    residents = requests_service(session)
    await residents.accept(own.user_id, request_id)
    rated = await residents.rate(own.user_id, request_id, 5, None)

    assert rated.request.completion_reason is RequestCompletionReason.RESIDENT_ACCEPTED
    assert rated.request.rating == 5
    await publisher.flush()
    assert [
        message["user_id"] for message in broker.enqueued(TaskName.SEND_TO_USER)
    ] == [own.user_id, own.user_id]
    assert broker.enqueued(TaskName.SEND_REVIEW_CARD) == [{"request_id": request_id}]


async def test_a_phone_request_refuses_a_resident_of_another_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    foreign = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)

    with pytest.raises(EntityNotFound):
        await admin_requests_service(session).create_phone(
            own.org_id,
            _phone_draft(own, resident_id=await _resident_id(session, foreign)),
            await _member(session, own.org_id, OrgRole.EMPLOYEE),
        )


async def test_a_phone_request_refuses_a_blocked_resident(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    residents = ResidentsRepo(session)
    resident = await residents.get(await _resident_id(session, own))
    assert resident is not None
    await residents.set_status(resident, ResidentStatus.BLOCKED, "Задолженность")

    with pytest.raises(InvalidState, match=RESIDENT_BLOCKED):
        await admin_requests_service(session).create_phone(
            own.org_id,
            _phone_draft(own, resident_id=resident.id),
            await _member(session, own.org_id, OrgRole.EMPLOYEE),
        )


async def test_a_phone_request_refuses_a_flat_other_than_the_residents(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    other = Flat(house_id=own.house_id, number="2")
    session.add(other)
    await session.flush()

    with pytest.raises(InvalidRequest):
        await admin_requests_service(session).create_phone(
            own.org_id,
            _phone_draft(
                own,
                resident_id=await _resident_id(session, own),
                flat_id=other.id,
            ),
            await _member(session, own.org_id, OrgRole.EMPLOYEE),
        )


async def test_repeating_the_current_status_changes_nothing(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request_id = (await _complain(session, own.user_id, own.house_id)).id
    service = admin_requests_service(session)
    await service.change_status(
        own.org_id,
        request_id,
        RequestStatus.ACCEPTED,
        None,
        staff,
    )

    card = await service.change_status(
        own.org_id,
        request_id,
        RequestStatus.ACCEPTED,
        "Еще раз",
        staff,
    )

    assert card.card.request.status is RequestStatus.ACCEPTED
    assert not card.card.messages
    assert await _logs(session, request_id) == [
        RequestStatus.NEW,
        RequestStatus.ACCEPTED,
    ]
    assert len(await events_of(session, EventType.REQUEST_STATUS_CHANGED)) == 1
    with pytest.raises(InvalidState):
        await service.change_status(
            own.org_id,
            request_id,
            RequestStatus.NEW,
            None,
            staff,
        )


async def test_change_status_rereads_a_status_moved_meanwhile(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request.id)
        .values(status=RequestStatus.ACCEPTED)
    )
    await session.execute(stmt)

    await admin_requests_service(session).change_status(
        own.org_id,
        request.id,
        RequestStatus.ACCEPTED,
        None,
        staff,
    )

    assert await _logs(session, request.id) == [RequestStatus.NEW]


@pytest.mark.parametrize(
    ("user", "moved"),
    [(API_CHECKER, False), (_STAFF_INIT_DATA, True)],
    ids=["checker", "staff"],
)
async def test_the_checker_takes_its_own_request_no_further_than_accepted(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    user: WebAppInitData,
    moved: bool,
) -> None:
    request = await _complain(session, own.user_id, own.house_id)
    org = CurrentOrg(
        org_id=own.org_id,
        user_id=own.user_id,
        role=OrgRole.EMPLOYEE,
        is_demo=False,
    )
    service = admin_requests_service(session)
    files = FilesService(make_config().files, "test-token")

    async def move(status: RequestStatus) -> AdminRequestCard:
        body = ChangeRequestStatusRequest(status=status)
        return await change_request_status(request.id, org, service, files, body, user)

    await move(RequestStatus.ACCEPTED)
    if moved:
        card = await move(RequestStatus.IN_PROGRESS)
        assert card.status is RequestStatus.IN_PROGRESS
    else:
        with pytest.raises(NotEnoughRights):
            await move(RequestStatus.IN_PROGRESS)


async def test_a_declining_executor_hands_the_request_back_with_an_internal_reason(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request_id, executor = await _in_progress(session, own)

    await admin_requests_service(session, publisher).executor_decline(
        executor,
        request_id,
        "  Уехал на другой вызов ",
    )

    admin_card = await admin_requests_service(session).card(own.org_id, request_id)
    request = admin_card.card.request
    assert request.executor_user_id is None
    assert request.status is RequestStatus.IN_PROGRESS
    [note] = admin_card.card.messages
    assert note.message.text == "Уехал на другой вызов"
    assert note.message.is_internal
    assert note.message.author_role == RequestActorRole.EXECUTOR.value
    resident_card = await requests_service(session).get_card(own.user_id, request_id)
    assert resident_card.messages == []
    declined = await events_of(session, EventType.EXECUTOR_DECLINED)
    assert [(event.user_id, event.payload) for event in declined] == [
        (executor, {"request_id": request_id, "status": "in_progress"}),
    ]
    await publisher.flush()
    [broadcast] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert broadcast["user_ids"] == [staff]
    assert "Уехал на другой вызов" in broadcast["text"]
    assert broadcast["app_path"] == f"/admin/requests/{request_id}"
    assert broker.enqueued(TaskName.SEND_EXECUTOR_CARD) == [
        {"request_id": request_id, "user_id": executor},
    ]
    assert broker.enqueued(TaskName.SEND_TO_USER) == []


@pytest.mark.parametrize("loss", ["another_executor", "removed", "demoted"])
async def test_only_the_assigned_executor_of_the_org_can_decline(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    loss: str,
) -> None:
    request_id, executor = await _assigned(session, own)
    orgs_repo = OrgsRepo(session)
    member = await orgs_repo.get_member(own.org_id, executor)
    assert member is not None
    actor = executor
    if loss == "another_executor":
        actor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    elif loss == "removed":
        await orgs_repo.remove_member(member)
    else:
        await orgs_repo.set_member_role(member, OrgRole.EMPLOYEE)

    with pytest.raises(NotEnoughRights):
        await admin_requests_service(session).executor_decline(
            actor,
            request_id,
            "Не успеваю",
        )

    card = await admin_requests_service(session).card(own.org_id, request_id)
    assert card.card.request.executor_user_id == executor
    assert card.card.messages == []


async def test_a_request_handed_in_for_review_cannot_be_declined(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id, executor = await _in_progress(session, own)
    service = admin_requests_service(session)
    await service.executor_advance(
        executor,
        request_id,
        RequestStatus.ON_REVIEW,
        [photo_name()],
    )

    with pytest.raises(InvalidState):
        await service.executor_decline(executor, request_id, "Передумал")

    card = await service.card(own.org_id, request_id)
    assert card.card.request.executor_user_id == executor


async def test_a_decline_without_a_reason_is_refused(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id, executor = await _assigned(session, own)
    service = admin_requests_service(session)

    with pytest.raises(InvalidRequest):
        await service.executor_decline(executor, request_id, "   ")

    card = await service.card(own.org_id, request_id)
    assert card.card.request.executor_user_id == executor


async def test_a_new_request_goes_straight_to_the_category_executor(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    await category_executors_service(session).set(
        own.org_id,
        RequestCategory.ELEVATOR,
        executor,
    )
    service = requests_service(session, publisher)
    draft = RequestDraft(category=RequestCategory.ELEVATOR, description="Застрял")

    lift = await service.create(own.user_id, own.house_id, draft)
    leak = await service.create(
        own.user_id,
        own.house_id,
        RequestDraft(category=RequestCategory.LEAK, description="Течет"),
    )

    assert lift.request.executor_user_id == executor
    assert lift.request.status is RequestStatus.NEW
    assert leak.request.executor_user_id is None
    assigned = await events_of(session, EventType.REQUEST_ASSIGNED)
    assert [(event.user_id, event.payload) for event in assigned] == [
        (None, {"request_id": lift.request.id, "executor_user_id": executor}),
    ]
    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_EXECUTOR_CARD) == [
        {"request_id": lift.request.id, "user_id": None},
    ]


async def test_repeat_and_phone_requests_go_to_the_category_executor(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    await category_executors_service(session).set(
        own.org_id,
        RequestCategory.LEAK,
        executor,
    )

    phone = await admin_requests_service(session).create_phone(
        own.org_id,
        _phone_draft(own, resident_id=await _resident_id(session, own)),
        staff,
    )
    parent_id = phone.card.request.id
    service = admin_requests_service(session)
    for target in TO_REVIEW:
        await service.change_status(own.org_id, parent_id, target, None, staff)
    repeat = await requests_service(session).reject(
        own.user_id,
        parent_id,
        "Снова течет",
        RequestChannel.MINIAPP,
    )

    assert phone.card.request.executor_user_id == executor
    assert repeat.request.executor_user_id == executor


async def test_a_category_executor_who_is_no_longer_an_executor_gets_nothing(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    categories = category_executors_service(session)
    await categories.set(own.org_id, RequestCategory.LEAK, executor)
    orgs_repo = OrgsRepo(session)
    member = await orgs_repo.get_member(own.org_id, executor)
    assert member is not None
    await orgs_repo.set_member_role(member, OrgRole.EMPLOYEE)

    request = await _complain(session, own.user_id, own.house_id)

    assert request.executor_user_id is None
    assert await categories.mapping(own.org_id) == {}


async def test_a_category_executor_must_be_an_executor_of_the_org(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    foreign = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    alien = await _member(session, foreign.org_id, OrgRole.EXECUTOR)
    categories = category_executors_service(session)

    with pytest.raises(InvalidRequest):
        await categories.set(own.org_id, RequestCategory.LEAK, staff)
    with pytest.raises(EntityNotFound):
        await categories.set(own.org_id, RequestCategory.LEAK, alien)

    assert await OrgsRepo(session).list_category_executors(own.org_id) == {}


async def test_a_category_executor_is_replaced_and_cleared(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    first = await _member(session, own.org_id, OrgRole.EXECUTOR)
    second = await _member(session, own.org_id, OrgRole.EXECUTOR)
    categories = category_executors_service(session)

    await categories.set(own.org_id, RequestCategory.LEAK, first)
    replaced = await categories.set(own.org_id, RequestCategory.LEAK, second)
    cleared = await categories.set(own.org_id, RequestCategory.LEAK, None)

    assert replaced == {RequestCategory.LEAK: second}
    assert cleared == {}


def test_only_an_admin_sets_a_category_executor() -> None:
    guards = {
        method: _calls(route.dependant)
        for route in admin_orgs_router.routes
        if isinstance(route, APIRoute) and route.path == "/admin/org/category-executors"
        for method in route.methods or ()
    }

    assert require_admin_org in guards["PUT"]
    assert require_admin_org not in guards["GET"]


def _calls(dependant: Dependant) -> set[object]:
    calls: set[object] = {dependant.call}
    for dependency in dependant.dependencies:
        calls |= _calls(dependency)
    return calls


async def test_a_category_executor_is_unset_when_removed_or_no_longer_an_executor(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    removed = await _member(session, own.org_id, OrgRole.EXECUTOR)
    promoted = await _member(session, own.org_id, OrgRole.EXECUTOR)
    kept = await _member(session, own.org_id, OrgRole.EXECUTOR)
    categories = category_executors_service(session)
    await categories.set(own.org_id, RequestCategory.LEAK, removed)
    await categories.set(own.org_id, RequestCategory.ELEVATOR, promoted)
    await categories.set(own.org_id, RequestCategory.HEATING, kept)
    orgs = make_orgs_service(session)
    invite = await orgs.create_invite(
        own.org_id,
        own.user_id,
        OrgRole.CREATOR,
        OrgRole.EMPLOYEE,
        1,
        1,
    )

    await orgs.remove_member(own.org_id, OrgRole.CREATOR, removed)
    await orgs.activate_invite(promoted, invite.code)

    assert await OrgsRepo(session).list_category_executors(own.org_id) == {
        RequestCategory.HEATING: kept,
    }


@pytest.mark.parametrize(
    "build",
    [
        lambda quote: texts.request_reply(RequestId(1), RequestCategory.LEAK, quote),
        lambda quote: texts.executor_declined(
            RequestId(1),
            RequestCategory.LEAK,
            "Иван",
            quote,
        ),
    ],
)
def test_a_quoted_free_text_is_cut_to_fit_a_max_message(
    build: Callable[[str], str],
) -> None:
    quote = f"<&>{'😀' * 2500}"

    text = build(quote)

    units = len(text.encode("utf-16-le")) // 2
    assert texts.MESSAGE_LIMIT - 2 < units <= texts.MESSAGE_LIMIT
    assert "&lt;&amp;&gt;😀" in text
    assert "😀…" in text
    assert "…" not in build("Уехал на другой вызов")
