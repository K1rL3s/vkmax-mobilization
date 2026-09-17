import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser, make_config

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
from zheka.core.errors import EntityNotFound, InvalidRequest, InvalidState
from zheka.core.ids import (
    FlatId,
    HouseId,
    MaxUserId,
    OrgId,
    RequestId,
    UserId,
)
from zheka.core.models import Request
from zheka.core.services.admin_requests import (
    AdminRequestsService,
    PhoneRequestDraft,
)
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.request_groups import GroupingService
from zheka.core.services.requests import RequestDraft, RequestsService
from zheka.infra.database.models import Event, Flat, OrgMember, Resident, User
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestFilters, RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.events import events_table
from zheka.infra.database.tables.requests import (
    request_status_log_table,
    requests_table,
)

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]

NO_FILTERS = RequestFilters()


def _admin(session: AsyncSession) -> AdminRequestsService:
    return AdminRequestsService(
        RequestsRepo(session),
        HousesRepo(session),
        UsersRepo(session),
        OrgsRepo(session),
        GroupingService(RequestsRepo(session), EventsService(EventsRepo(session))),
        EventsService(EventsRepo(session)),
    )


def _resident_service(session: AsyncSession) -> RequestsService:
    return RequestsService(
        RequestsRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        UsersRepo(session),
        OrgsRepo(session),
        FilesService(make_config().files, "test-token"),
        GroupingService(RequestsRepo(session), EventsService(EventsRepo(session))),
        EventsService(EventsRepo(session)),
    )


async def _complain(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    category: RequestCategory = RequestCategory.LEAK,
) -> Request:
    card = await _resident_service(session).create(
        user_id,
        house_id,
        RequestDraft(category=category, description="Течет стояк"),
    )
    return card.request


async def _member(
    session: AsyncSession,
    org_id: OrgId,
    role: OrgRole,
) -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name="Сотрудник")
    session.add(user)
    await session.flush()
    session.add(OrgMember(org_id=org_id, user_id=user.id, role=role))
    await session.flush()
    return UserId(user.id)


async def _neighbour(session: AsyncSession, house_id: HouseId, number: str) -> UserId:
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


async def _age(session: AsyncSession, request_id: RequestId, hours: int) -> None:
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(created_at=datetime.now(UTC) - timedelta(hours=hours))
    )
    await session.execute(stmt)
    await session.flush()


async def _logs(session: AsyncSession, request_id: RequestId) -> list[RequestStatus]:
    stmt = (
        select(request_status_log_table.c.to_status)
        .where(request_status_log_table.c.request_id == request_id)
        .order_by(request_status_log_table.c.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _events(session: AsyncSession, type_: EventType) -> list[Event]:
    stmt = select(Event).where(events_table.c.type == type_)
    return list((await session.execute(stmt)).scalars().all())


async def test_inbox_never_shows_a_request_of_another_organization(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    mine = await _complain(session, own.user_id, own.house_id)
    await _complain(session, foreign.user_id, foreign.house_id)

    rows, total = await _admin(session).inbox(own.org_id, NO_FILTERS, 20, 0)

    assert total == 1
    assert [row.request.id for row in rows] == [mine.id]


async def test_a_request_of_another_organization_is_not_found_by_id(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    alien = await _complain(session, foreign.user_id, foreign.house_id)

    # чужая заявка отвечает 404, а не 403
    with pytest.raises(EntityNotFound):
        await _admin(session).card(own.org_id, RequestId(alien.id))


async def test_overdue_requests_come_first_and_can_be_filtered(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    fresh = await _complain(session, own.user_id, own.house_id)
    second = await _neighbour(session, own.house_id, "2")
    late = await _complain(session, second, own.house_id)
    normative = CATEGORY_RULES[RequestCategory.LEAK].normative_hours
    await _age(session, RequestId(late.id), normative + 1)
    service = _admin(session)

    rows, _ = await service.inbox(own.org_id, NO_FILTERS, 20, 0)
    only_overdue, total = await service.inbox(
        own.org_id,
        RequestFilters(overdue=True),
        20,
        0,
    )

    assert [row.request.id for row in rows] == [late.id, fresh.id]
    assert total == 1
    assert [row.request.id for row in only_overdue] == [late.id]


async def test_a_done_request_is_never_overdue(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    old = await _complain(session, own.user_id, own.house_id)
    await _age(session, RequestId(old.id), 1000)
    old.status = RequestStatus.DONE
    await session.flush()

    rows, total = await _admin(session).inbox(
        own.org_id,
        RequestFilters(overdue=True),
        20,
        0,
    )

    assert total == 0
    assert rows == []


async def test_grouped_collapses_a_group_into_one_row(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    first = await _complain(session, own.user_id, own.house_id)
    for number in ("2", "3"):
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
        )
    service = _admin(session)

    plain, plain_total = await service.inbox(own.org_id, NO_FILTERS, 20, 0)
    collapsed, collapsed_total = await service.inbox(
        own.org_id,
        RequestFilters(grouped=True),
        20,
        0,
    )

    assert plain_total == 3
    assert len(plain) == 3
    # группа схлопывается в самую раннюю заявку, размер группы виден в строке
    assert collapsed_total == 1
    assert [row.request.id for row in collapsed] == [first.id]
    assert collapsed[0].group_size == 3


async def test_change_status_writes_the_log_the_stamp_and_the_event(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)
    request_id = RequestId(request.id)

    card = await _admin(session).change_status(
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
    # пояснение к статусу приезжает жителю как ответ УК
    assert [message.message.text for message in card.card.messages] == [
        "Приняли, выехали",
    ]
    events = await _events(session, EventType.REQUEST_STATUS_CHANGED)
    assert events[0].payload == {
        "request_id": request_id,
        "from": RequestStatus.NEW.value,
        "to": RequestStatus.ACCEPTED.value,
        "by_role": RequestActorRole.STAFF.value,
    }


async def test_change_status_refuses_to_move_backwards(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)
    request_id = RequestId(request.id)
    service = _admin(session)
    await service.change_status(
        own.org_id,
        request_id,
        RequestStatus.ACCEPTED,
        None,
        staff,
    )

    with pytest.raises(InvalidState):
        await service.change_status(
            own.org_id,
            request_id,
            RequestStatus.NEW,
            None,
            staff,
        )


async def test_staff_cannot_close_a_request_that_has_an_author(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)
    request_id = RequestId(request.id)
    service = _admin(session)
    for target in (
        RequestStatus.ACCEPTED,
        RequestStatus.IN_PROGRESS,
        RequestStatus.ON_REVIEW,
    ):
        await service.change_status(own.org_id, request_id, target, None, staff)

    # «Готово» от исполнителя не закрывает заявку, ее закрывает житель
    with pytest.raises(InvalidState):
        await service.change_status(
            own.org_id,
            request_id,
            RequestStatus.DONE,
            None,
            staff,
        )


async def test_staff_closes_a_phone_request_that_has_no_author(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = _admin(session)
    created = await service.create_phone(
        own.org_id,
        PhoneRequestDraft(
            house_id=own.house_id,
            category=RequestCategory.LEAK,
            description="Звонила Мария Ивановна, течет в подвале",
            caller_name="Мария Ивановна",
            caller_phone="+70000000000",
        ),
        staff,
    )
    request_id = RequestId(created.card.request.id)
    for target in (
        RequestStatus.ACCEPTED,
        RequestStatus.IN_PROGRESS,
        RequestStatus.ON_REVIEW,
    ):
        await service.change_status(own.org_id, request_id, target, None, staff)

    card = await service.change_status(
        own.org_id,
        request_id,
        RequestStatus.DONE,
        None,
        staff,
    )

    assert card.card.request.status is RequestStatus.DONE


async def test_phone_request_carries_the_caller_and_no_author(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)

    card = await _admin(session).create_phone(
        own.org_id,
        PhoneRequestDraft(
            house_id=own.house_id,
            category=RequestCategory.ELEVATOR,
            description="Застрял лифт",
            flat_id=own.flat_id,
            caller_name="Мария Ивановна",
            caller_phone="+70000000000",
        ),
        staff,
    )

    request = card.card.request
    assert request.channel is RequestChannel.PHONE
    assert request.is_staff_author is True
    assert request.author_user_id is None
    assert request.caller_name == "Мария Ивановна"
    assert request.flat_id == own.flat_id
    assert await _logs(session, RequestId(request.id)) == [RequestStatus.NEW]


async def test_phone_request_refuses_a_house_of_another_organization(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    foreign = await make_org_house_flat_user()

    with pytest.raises(EntityNotFound):
        await _admin(session).create_phone(
            own.org_id,
            PhoneRequestDraft(
                house_id=foreign.house_id,
                category=RequestCategory.LEAK,
                description="Течет",
            ),
            await _member(session, own.org_id, OrgRole.EMPLOYEE),
        )


async def test_reply_writes_a_message_from_the_management(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)

    card = await _admin(session).reply(
        own.org_id,
        RequestId(request.id),
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
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)

    with pytest.raises(InvalidRequest):
        await _admin(session).reply(own.org_id, RequestId(request.id), "   ", staff)


async def test_assign_takes_an_executor_and_leaves_the_status_alone(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)

    card = await _admin(session).assign(
        own.org_id,
        RequestId(request.id),
        executor,
        staff,
    )

    assert card.card.request.executor_user_id == executor
    # в работу заявку переводит исполнитель, когда берет ее
    assert card.card.request.status is RequestStatus.NEW
    assert await _events(session, EventType.REQUEST_ASSIGNED) != []


async def test_assign_refuses_a_member_who_is_not_an_executor(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _complain(session, own.user_id, own.house_id)

    with pytest.raises(InvalidRequest):
        await _admin(session).assign(own.org_id, RequestId(request.id), staff, staff)


async def test_assign_refuses_an_executor_of_another_organization(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    alien = await _member(session, foreign.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)

    with pytest.raises(EntityNotFound):
        await _admin(session).assign(own.org_id, RequestId(request.id), alien, staff)


async def test_executors_are_listed_with_their_load(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)
    service = _admin(session)
    await service.assign(own.org_id, RequestId(request.id), executor, staff)

    views = await service.executors(own.org_id)

    # сотрудник кабинета в списке исполнителей не появляется
    assert [UserId(view.user.id) for view in views] == [executor]
    assert views[0].active_requests == 1


async def test_group_status_moves_every_member_and_logs_each(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    members = [await _complain(session, own.user_id, own.house_id)]
    members += [
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
        )
        for number in ("2", "3")
    ]
    group_id = members[-1].group_id
    assert group_id is not None
    service = _admin(session)

    card = await service.change_group_status(
        own.org_id,
        group_id,
        RequestStatus.ACCEPTED,
        "Приняли всю группу",
        staff,
    )

    assert card.flats_count == 3
    assert len(card.rows) == 3
    assert all(row.request.status is RequestStatus.ACCEPTED for row in card.rows)
    for member in members:
        assert await _logs(session, RequestId(member.id)) == [
            RequestStatus.NEW,
            RequestStatus.ACCEPTED,
        ]


async def test_closing_a_group_closes_the_group_row(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = _admin(session)
    for number in ("11", "12", "13"):
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
        )
    rows, _ = await service.inbox(own.org_id, NO_FILTERS, 20, 0)
    group_id = rows[0].request.group_id
    assert group_id is not None
    for target in (
        RequestStatus.ACCEPTED,
        RequestStatus.IN_PROGRESS,
        RequestStatus.ON_REVIEW,
    ):
        await service.change_group_status(own.org_id, group_id, target, None, staff)

    # у заявок группы есть авторы, поэтому закрывает их житель, а не УК
    with pytest.raises(InvalidState):
        await service.change_group_status(
            own.org_id,
            group_id,
            RequestStatus.DONE,
            None,
            staff,
        )


async def test_a_group_of_another_organization_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    foreign = await make_org_house_flat_user()
    for number in ("11", "12", "13"):
        await _complain(
            session,
            await _neighbour(session, foreign.house_id, number),
            foreign.house_id,
        )
    rows, _ = await _admin(session).inbox(foreign.org_id, NO_FILTERS, 20, 0)
    group_id = rows[0].request.group_id
    assert group_id is not None

    with pytest.raises(EntityNotFound):
        await _admin(session).group_card(own.org_id, group_id)


async def test_a_group_already_in_the_target_status_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    for number in ("11", "12", "13"):
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
        )
    service = _admin(session)
    rows, _ = await service.inbox(own.org_id, NO_FILTERS, 20, 0)
    group_id = rows[0].request.group_id
    assert group_id is not None
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


async def test_the_group_row_closes_when_the_phone_requests_are_done(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = _admin(session)
    flats = [own.flat_id]
    for number in ("2", "3"):
        flat = Flat(house_id=own.house_id, number=number)
        session.add(flat)
        await session.flush()
        flats.append(FlatId(flat.id))
    for flat_id in flats:
        await service.create_phone(
            own.org_id,
            PhoneRequestDraft(
                house_id=own.house_id,
                category=RequestCategory.LEAK,
                description="Течет по стояку",
                flat_id=flat_id,
                caller_name="Жилец",
                caller_phone="+70000000000",
            ),
            staff,
        )
    rows, _ = await service.inbox(own.org_id, NO_FILTERS, 20, 0)
    group_id = rows[0].request.group_id
    assert group_id is not None
    for target in (
        RequestStatus.ACCEPTED,
        RequestStatus.IN_PROGRESS,
        RequestStatus.ON_REVIEW,
    ):
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


async def test_group_status_skips_a_member_that_is_already_there(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = _admin(session)
    for number in ("11", "12", "13"):
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
        )
    rows, _ = await service.inbox(own.org_id, NO_FILTERS, 20, 0)
    group_id = rows[0].request.group_id
    assert group_id is not None
    ahead = RequestId(rows[0].request.id)
    await service.change_status(
        own.org_id,
        ahead,
        RequestStatus.ACCEPTED,
        None,
        staff,
    )

    card = await service.change_group_status(
        own.org_id,
        group_id,
        RequestStatus.ACCEPTED,
        None,
        staff,
    )

    # заявку, ушедшую вперед, группа не двигает второй раз и не падает из-за
    # нее целиком: статусы внутри группы расходятся штатно
    assert all(row.request.status is RequestStatus.ACCEPTED for row in card.rows)
    assert await _logs(session, ahead) == [RequestStatus.NEW, RequestStatus.ACCEPTED]
