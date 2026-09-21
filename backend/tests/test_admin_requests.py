import secrets

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser, RecordingBroker
from tests.test_requests import (
    Fixture,
    _admin,
    _age,
    _complain,
    _events,
    _group_of_three,
    _member,
    _neighbour,
)

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import (
    CATEGORY_RULES,
    EventType,
    OrgRole,
    RequestActorRole,
    RequestCategory,
    RequestChannel,
    RequestGroupStatus,
    RequestStatus,
    ResidentRole,
)
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import RequestId, UserId
from zheka.core.services.admin_requests import PhoneRequestDraft
from zheka.infra.database.models import Flat
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestFilters
from zheka.infra.database.tables.requests import request_status_log_table

NO_FILTERS = RequestFilters()
TO_REVIEW = (RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS, RequestStatus.ON_REVIEW)


async def _logs(session: AsyncSession, request_id: RequestId) -> list[RequestStatus]:
    stmt = (
        select(request_status_log_table.c.to_status)
        .where(request_status_log_table.c.request_id == request_id)
        .order_by(request_status_log_table.c.id)
    )
    return list((await session.execute(stmt)).scalars().all())


def _phone_draft(own: OrgHouseFlatUser, **fields: object) -> PhoneRequestDraft:
    return PhoneRequestDraft(
        house_id=own.house_id,
        category=RequestCategory.LEAK,
        description="Течет",
        **fields,  # type: ignore[arg-type]
    )


async def test_inbox_never_shows_a_request_of_another_organization(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    mine = await _complain(session, own.user_id, own.house_id)
    await _complain(session, foreign.user_id, foreign.house_id)

    rows, total = await _admin(session).inbox(own.org_id, NO_FILTERS, 20, 0)

    assert total == 1
    assert [row.request.id for row in rows] == [mine.id]


async def test_a_request_of_another_organization_is_not_found_by_id(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    alien = await _complain(session, foreign.user_id, foreign.house_id)

    # чужая заявка отвечает 404, а не 403
    with pytest.raises(EntityNotFound):
        await _admin(session).card(own.org_id, alien.id)


async def test_overdue_requests_come_first_and_can_be_filtered(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    fresh = await _complain(session, own.user_id, own.house_id)
    late = await _complain(session, own.user_id, own.house_id)
    done = await _complain(session, own.user_id, own.house_id)
    normative = CATEGORY_RULES[RequestCategory.LEAK].normative_hours
    await _age(session, late.id, normative + 1)
    await _age(session, done.id, normative + 2)
    done.status = RequestStatus.DONE
    await session.flush()
    service = _admin(session)

    rows, _ = await service.inbox(own.org_id, NO_FILTERS, 20, 0)
    only_overdue, total = await service.inbox(
        own.org_id, RequestFilters(overdue=True), 20, 0
    )

    # выполненная заявка не просрочена, как бы давно ее ни подали
    assert [row.request.id for row in rows] == [late.id, fresh.id, done.id]
    assert total == 1
    assert [row.request.id for row in only_overdue] == [late.id]


async def test_grouped_collapses_a_group_into_one_row(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user()
    members, _ = await _group_of_three(session, own)
    service = _admin(session)

    plain, plain_total = await service.inbox(own.org_id, NO_FILTERS, 20, 0)
    collapsed, collapsed_total = await service.inbox(
        own.org_id, RequestFilters(grouped=True), 20, 0
    )

    assert plain_total == 3
    assert len(plain) == 3
    # группа схлопывается в самую раннюю заявку, размер группы виден в строке
    assert collapsed_total == 1
    assert [row.request.id for row in collapsed] == [members[0].id]
    assert collapsed[0].group_size == 3


async def test_change_status_writes_the_log_the_stamp_and_the_event(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)
    request_id = request.id

    card = await _admin(session).change_status(
        own.org_id, request_id, RequestStatus.ACCEPTED, "Приняли, выехали", staff
    )

    assert card.card.request.status is RequestStatus.ACCEPTED
    assert card.card.request.accepted_at is not None
    assert await _logs(session, request_id) == [
        RequestStatus.NEW,
        RequestStatus.ACCEPTED,
    ]
    # пояснение к статусу приезжает жителю как ответ УК
    assert [message.message.text for message in card.card.messages] == [
        "Приняли, выехали"
    ]
    events = await _events(session, EventType.REQUEST_STATUS_CHANGED)
    assert events[0].payload == {
        "request_id": request_id,
        "from": RequestStatus.NEW.value,
        "to": RequestStatus.ACCEPTED.value,
        "by_role": RequestActorRole.STAFF.value,
    }


async def test_phone_request_carries_the_caller_and_no_author(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)

    card = await _admin(session).create_phone(
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


async def test_phone_request_accepts_a_flat_without_caller_details(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)

    card = await _admin(session).create_phone(
        own.org_id, _phone_draft(own, flat_id=own.flat_id), staff
    )

    assert card.card.request.flat_id == own.flat_id
    assert card.card.request.caller_name is None
    assert card.card.request.caller_phone is None


async def test_phone_request_refuses_without_a_flat_or_full_caller_details(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = _admin(session)

    for fields in ({}, {"caller_name": "Мария"}, {"caller_phone": "+70000000000"}):
        with pytest.raises(InvalidRequest):
            await service.create_phone(own.org_id, _phone_draft(own, **fields), staff)


async def test_phone_request_refuses_a_house_of_another_organization(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user()
    foreign = await make_org_house_flat_user()

    with pytest.raises(EntityNotFound):
        await _admin(session).create_phone(
            own.org_id,
            _phone_draft(foreign, flat_id=foreign.flat_id),
            await _member(session, own.org_id, OrgRole.EMPLOYEE),
        )


async def test_reply_writes_a_message_from_the_management(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)

    card = await _admin(session).reply(
        own.org_id, request.id, "  Мастер придет завтра  ", staff
    )

    assert [message.message.text for message in card.card.messages] == [
        "Мастер придет завтра"
    ]
    assert card.card.messages[0].message.author_role == RequestActorRole.STAFF
    assert card.card.messages[0].author is not None


async def test_reply_refuses_an_empty_text(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)

    with pytest.raises(InvalidRequest):
        await _admin(session).reply(own.org_id, request.id, "   ", staff)


async def test_assign_takes_an_executor_leaves_the_status_and_opens_his_card(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)

    card = await _admin(session, publisher).assign(
        own.org_id, request.id, executor, staff
    )

    assert card.card.request.executor_user_id == executor
    # в работу заявку переводит исполнитель, когда берет ее
    assert card.card.request.status is RequestStatus.NEW
    assert await _events(session, EventType.REQUEST_ASSIGNED) != []
    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_EXECUTOR_CARD) == [
        {"request_id": request.id, "user_id": None}
    ]


async def test_assign_refuses_a_member_who_is_not_an_executor(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)

    with pytest.raises(InvalidRequest):
        await _admin(session).assign(own.org_id, request.id, staff, staff)


async def test_assign_refuses_an_executor_of_another_organization(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    alien = await _member(session, foreign.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)

    with pytest.raises(EntityNotFound):
        await _admin(session).assign(own.org_id, request.id, alien, staff)


async def test_executors_are_listed_with_their_load(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)
    service = _admin(session)
    await service.assign(own.org_id, request.id, executor, staff)

    views = await service.executors(own.org_id)

    # сотрудник кабинета в списке исполнителей не появляется
    assert [view.user.id for view in views] == [executor]
    assert views[0].active_requests == 1


async def test_staff_cannot_close_a_group_whose_requests_have_authors(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = _admin(session)
    _, group_id = await _group_of_three(session, own)
    for target in TO_REVIEW:
        await service.change_group_status(own.org_id, group_id, target, None, staff)

    # «Готово» от исполнителя не закрывает заявку, ее закрывает житель
    with pytest.raises(InvalidState):
        await service.change_group_status(
            own.org_id, group_id, RequestStatus.DONE, None, staff
        )


async def test_a_group_of_another_organization_is_not_found(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user()
    foreign = await make_org_house_flat_user()
    _, group_id = await _group_of_three(session, foreign)

    with pytest.raises(EntityNotFound):
        await _admin(session).group_card(own.org_id, group_id)


async def test_a_group_already_in_the_target_status_is_refused(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    _, group_id = await _group_of_three(session, own)
    service = _admin(session)
    await service.change_group_status(
        own.org_id, group_id, RequestStatus.ACCEPTED, None, staff
    )

    with pytest.raises(InvalidState):
        await service.change_group_status(
            own.org_id, group_id, RequestStatus.ACCEPTED, None, staff
        )


async def test_staff_closes_a_group_of_phone_requests_and_its_row(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = _admin(session)
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
        own.org_id, group_id, RequestStatus.DONE, None, staff
    )

    assert card.group.status is RequestGroupStatus.CLOSED
    assert all(row.request.status is RequestStatus.DONE for row in card.rows)


async def test_group_status_carries_a_late_joiner_through_two_steps(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    members, group_id = await _group_of_three(session, own)
    service = _admin(session)
    for target in (RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS):
        await service.change_group_status(own.org_id, group_id, target, None, staff)

    # группа остается OPEN сквозь ACCEPTED/IN_PROGRESS, поэтому свежая жалоба
    # вступает в нее и стартует с NEW, пока остальные уже в IN_PROGRESS
    latecomer = await _complain(
        session, await _neighbour(session, own.house_id, "4"), own.house_id
    )
    assert latecomer.group_id == group_id
    assert latecomer.status is RequestStatus.NEW

    card = await service.change_group_status(
        own.org_id, group_id, RequestStatus.IN_PROGRESS, "Работаем", staff
    )

    assert card.flats_count == 4
    assert len(card.rows) == 4
    assert all(row.request.status is RequestStatus.IN_PROGRESS for row in card.rows)
    # опоздавший идет двумя шагами, ушедшие вперед второй раз не двигаются
    for member in [*members, latecomer]:
        assert await _logs(session, member.id) == [
            RequestStatus.NEW,
            RequestStatus.ACCEPTED,
            RequestStatus.IN_PROGRESS,
        ]
    # комментарий сопровождает только последний шаг, а не каждый промежуточный
    latecomer_card = await service.card(own.org_id, latecomer.id)
    assert [message.message.text for message in latecomer_card.card.messages] == [
        "Работаем"
    ]


async def test_group_status_refuses_a_member_ahead_of_the_target(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    members, group_id = await _group_of_three(session, own)
    service = _admin(session)
    ahead = members[0].id
    for target in (RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS):
        await service.change_status(own.org_id, ahead, target, None, staff)

    # участник обогнал цель, назад его никто не двигает: вызов падает целиком
    with pytest.raises(InvalidState):
        await service.change_group_status(
            own.org_id, group_id, RequestStatus.ACCEPTED, None, staff
        )

    for member in members[1:]:
        assert await _logs(session, member.id) == [RequestStatus.NEW]


async def _assigned(
    session: AsyncSession, own: OrgHouseFlatUser
) -> tuple[RequestId, UserId]:
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)
    request_id = request.id
    await _admin(session).assign(own.org_id, request_id, executor, own.user_id)
    return request_id, executor


async def _in_progress(
    session: AsyncSession, own: OrgHouseFlatUser
) -> tuple[RequestId, UserId]:
    request_id, executor = await _assigned(session, own)
    service = _admin(session)
    await service.executor_advance(executor, request_id, RequestStatus.ACCEPTED, [])
    await service.executor_advance(executor, request_id, RequestStatus.IN_PROGRESS, [])
    return request_id, executor


def _photo_name() -> str:
    return f"{secrets.token_hex(16)}.jpg"


async def test_the_executor_accepts_a_new_request_assigned_to_him(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    # диспетчер, назначивший NEW, оставляет «принял» исполнителю
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    request_id, executor = await _assigned(session, own)

    await _admin(session).executor_advance(
        executor, request_id, RequestStatus.ACCEPTED, []
    )

    stmt = select(request_status_log_table).where(
        request_status_log_table.c.request_id == request_id,
        request_status_log_table.c.to_status == RequestStatus.ACCEPTED,
    )
    log = (await session.execute(stmt)).one()
    assert log.by_role == RequestActorRole.EXECUTOR
    assert log.by_user_id == executor
    events = await _events(session, EventType.EXECUTOR_STATUS_CHANGED)
    assert [event.payload for event in events] == [
        {"request_id": request_id, "to": RequestStatus.ACCEPTED.value}
    ]


async def test_ready_without_a_result_photo_is_refused_and_writes_nothing(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    request_id, executor = await _in_progress(session, own)

    with pytest.raises(InvalidState, match="фото результата"):
        await _admin(session).executor_advance(
            executor, request_id, RequestStatus.ON_REVIEW, []
        )

    assert (await _logs(session, request_id))[-1] is RequestStatus.IN_PROGRESS


async def test_ready_with_a_result_photo_opens_the_review_card(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    request_id, executor = await _in_progress(session, own)
    name = _photo_name()

    await _admin(session, publisher).executor_advance(
        executor, request_id, RequestStatus.ON_REVIEW, [name]
    )

    card = await _admin(session).executor_card(executor, request_id)
    assert card is not None
    assert card.request.status is RequestStatus.ON_REVIEW
    assert [photo.path for photo in card.result_photos] == [name]
    # карточка приемки заменяет текст статуса
    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_REVIEW_CARD) == [{"request_id": request_id}]
    assert broker.enqueued(TaskName.SEND_TO_USER) == []


async def test_a_refused_move_attaches_no_result_photo(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    # второе фото после того, как первое уже увело заявку на приемку: отказ
    # должен случиться до записи фото, задача ловит его и рисует карточку
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    request_id, executor = await _in_progress(session, own)
    service = _admin(session)
    await service.executor_advance(
        executor, request_id, RequestStatus.ON_REVIEW, [_photo_name()]
    )

    with pytest.raises(InvalidState):
        await service.executor_advance(
            executor, request_id, RequestStatus.ON_REVIEW, [_photo_name()]
        )

    card = await service.executor_card(executor, request_id)
    assert card is not None
    assert len(card.result_photos) == 1


@pytest.mark.parametrize("loss", ["another_executor", "removed", "demoted"])
async def test_only_the_assigned_executor_of_the_org_can_advance(
    session: AsyncSession, make_org_house_flat_user: Fixture, loss: str
) -> None:
    # executor_user_id у заявки остается, а власть над статусом - нет
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
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
        await _admin(session).executor_advance(
            executor, request_id, RequestStatus.ACCEPTED, []
        )
    assert await _admin(session).executor_card(executor, request_id) is None
