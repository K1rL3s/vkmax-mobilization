from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    OrgHouseFlatUser,
    RecordingBroker,
    add_resident,
    add_user,
    admin_requests_service,
    events_of,
    requests_service,
)
from tests.test_contact import _viewer
from tests.test_requests import _age, _block, _complain, _group_of_three, _member

from zheka.api.routes.admin.requests import list_org_requests
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import (
    CATEGORY_RULES,
    DangerKind,
    EventType,
    OrgRole,
    RequestCategory,
    RequestPlace,
    RequestStatus,
)
from zheka.core.errors import EntityNotFound, InvalidState, NotEnoughRights
from zheka.core.ids import MaxChatId, UserId
from zheka.core.services.requests import RequestDraft
from zheka.core.texts import REQUEST_PLACE_LINES
from zheka.infra.database.models import OrgMember, User
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestFilters
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.pdf import GjiComplaint, PdfDocument


async def test_escalation_reaches_everyone_on_the_request_once(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    creator = await _member(session, own.org_id, OrgRole.CREATOR)
    admin = await _member(session, own.org_id, OrgRole.ADMIN)
    employee = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    await _member(session, own.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)
    request.executor_user_id = executor
    await session.flush()
    late = request.deadline_at + timedelta(hours=4, minutes=10)

    card = await requests_service(session, publisher).escalate(
        own.user_id,
        request.id,
        late,
    )

    assert card.request.escalated_at == late
    [event] = await events_of(session, EventType.REQUEST_ESCALATED)
    assert event.user_id == own.user_id
    await publisher.flush()
    [staff] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert sorted(staff["user_ids"]) == sorted([creator, admin, employee])
    assert staff["text"].startswith("⬆️ Житель просит руководство вмешаться")
    assert f"№{request.id}" in staff["text"]
    assert "просрочена на 5 ч" in staff["text"]
    assert REQUEST_PLACE_LINES[RequestPlace.FLAT] in staff["text"]
    assert staff["mandatory"] is False
    assert staff["app_path"] == f"/admin/requests/{request.id}"
    author, crew = broker.enqueued(TaskName.SEND_TO_USER)
    assert author["user_id"] == own.user_id
    assert author["text"].startswith("⬆️ Руководство УК уведомлено")
    assert author["app_path"] == f"/requests/{request.id}"
    assert crew["user_id"] == executor
    assert crew["text"] == staff["text"]


async def test_an_author_from_the_management_hears_only_the_confirmation(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    session.add(OrgMember(org_id=own.org_id, user_id=own.user_id, role=OrgRole.ADMIN))
    admin = await _member(session, own.org_id, OrgRole.ADMIN)
    request = await _complain(session, own.user_id, own.house_id)
    request.executor_user_id = own.user_id
    await session.flush()

    await requests_service(session, publisher).escalate(
        own.user_id,
        request.id,
        request.deadline_at + timedelta(hours=1),
    )

    await publisher.flush()
    [staff] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert staff["user_ids"] == [admin]
    [author] = broker.enqueued(TaskName.SEND_TO_USER)
    assert author["user_id"] == own.user_id
    assert author["text"].startswith("⬆️ Руководство УК уведомлено")


async def test_a_second_escalation_is_refused(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own.user_id, own.house_id)
    service = requests_service(session)
    late = request.deadline_at + timedelta(hours=1)
    await service.escalate(own.user_id, request.id, late)

    with pytest.raises(InvalidState):
        await service.escalate(own.user_id, request.id, late)


async def test_a_request_within_its_term_is_not_escalated(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own.user_id, own.house_id)

    with pytest.raises(InvalidState):
        await requests_service(session).escalate(
            own.user_id,
            request.id,
            request.deadline_at - timedelta(minutes=1),
        )
    assert request.escalated_at is None


@pytest.mark.parametrize("status", [RequestStatus.ON_REVIEW, RequestStatus.DONE])
async def test_a_request_past_the_work_is_not_escalated(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    status: RequestStatus,
) -> None:
    request = await _complain(session, own.user_id, own.house_id)
    request.status = status
    await session.flush()

    with pytest.raises(InvalidState):
        await requests_service(session).escalate(
            own.user_id,
            request.id,
            request.deadline_at + timedelta(hours=1),
        )


async def test_someone_elses_request_is_not_found(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    neighbour = await add_user(session)
    await add_resident(session, neighbour, own.house_id, None)
    request = await _complain(session, own.user_id, own.house_id)

    with pytest.raises(EntityNotFound):
        await requests_service(session).escalate(
            neighbour,
            request.id,
            request.deadline_at + timedelta(hours=1),
        )


async def test_a_blocked_author_cannot_escalate(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own.user_id, own.house_id)
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights):
        await requests_service(session).escalate(
            own.user_id,
            request.id,
            request.deadline_at + timedelta(hours=1),
        )


async def test_escalated_open_requests_lead_the_inbox(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    fresh = await _complain(session, own.user_id, own.house_id)
    late = await _complain(session, own.user_id, own.house_id)
    escalated = await _complain(session, own.user_id, own.house_id)
    finished = await _complain(session, own.user_id, own.house_id)
    normative = CATEGORY_RULES[RequestCategory.LEAK].fix_hours
    await _age(session, late.id, normative + 1)
    await _age(session, escalated.id, normative + 2)
    await _age(session, finished.id, normative + 3)
    service = requests_service(session)
    now = datetime.now(UTC)
    await service.escalate(own.user_id, escalated.id, now)
    await service.escalate(own.user_id, finished.id, now)
    finished.status = RequestStatus.DONE
    await session.flush()

    rows, _ = await admin_requests_service(session).inbox(
        own.org_id,
        RequestFilters(),
        20,
        0,
    )

    assert [row.request.id for row in rows] == [
        escalated.id,
        late.id,
        fresh.id,
        finished.id,
    ]


async def test_a_group_rises_by_any_escalated_member(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    lone = await _complain(
        session,
        own.user_id,
        own.house_id,
        RequestCategory.ELEVATOR,
    )
    members, _ = await _group_of_three(session, own)
    normative = CATEGORY_RULES[RequestCategory.LEAK].fix_hours
    await _age(session, lone.id, CATEGORY_RULES[RequestCategory.ELEVATOR].fix_hours + 5)
    for member in members:
        await _age(session, member.id, normative + 1)
    now = datetime.now(UTC)
    last = members[-1]
    assert last.author_user_id is not None
    await requests_service(session).escalate(last.author_user_id, last.id, now)

    rows, _ = await admin_requests_service(session).inbox(
        own.org_id,
        RequestFilters(grouped=True),
        20,
        0,
    )

    assert [row.request.id for row in rows] == [members[0].id, lone.id]
    assert rows[0].escalated_at == now
    assert rows[1].escalated_at is None


async def test_a_group_shows_its_earliest_open_escalation(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    members, _ = await _group_of_three(session, own)
    normative = CATEGORY_RULES[RequestCategory.LEAK].fix_hours
    for member in members:
        await _age(session, member.id, normative + 1)
    now = datetime.now(UTC)
    service = requests_service(session)
    for shift, member in enumerate(members):
        assert member.author_user_id is not None
        await service.escalate(
            member.author_user_id,
            member.id,
            now + timedelta(minutes=shift),
        )
    members[0].status = RequestStatus.DONE
    await session.flush()

    [row], _ = await admin_requests_service(session).inbox(
        own.org_id,
        RequestFilters(grouped=True),
        20,
        0,
    )

    assert row.escalated_at == now + timedelta(minutes=1)


async def test_open_dangerous_requests_follow_the_escalated_ones(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    late = await _complain(session, own.user_id, own.house_id)
    escalated = await _complain(session, own.user_id, own.house_id)
    sparks = RequestDraft(
        category=RequestCategory.ELECTRICITY,
        description="Искрит щиток на площадке",
        place=RequestPlace.HOUSE,
    )
    service = requests_service(session)
    dangerous = await service.create(own.user_id, own.house_id, sparks)
    finished = await service.create(own.user_id, own.house_id, sparks)
    normative = CATEGORY_RULES[RequestCategory.LEAK].fix_hours
    await _age(session, late.id, normative + 1)
    await _age(session, escalated.id, normative + 2)
    await service.escalate(own.user_id, escalated.id, datetime.now(UTC))
    finished.request.status = RequestStatus.DONE
    await session.flush()

    rows, _ = await admin_requests_service(session).inbox(
        own.org_id,
        RequestFilters(),
        20,
        0,
    )

    assert [row.request.id for row in rows] == [
        escalated.id,
        dangerous.request.id,
        late.id,
        finished.request.id,
    ]


async def test_a_group_rises_and_shows_the_danger_of_any_open_member(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    members, group_id = await _group_of_three(session, own)
    lone = await _complain(
        session,
        own.user_id,
        own.house_id,
        RequestCategory.ELEVATOR,
    )
    socket = RequestDraft(
        category=RequestCategory.LEAK,
        description="Вода течет прямо в розетку",
        place=RequestPlace.FLAT,
    )
    dangerous = await requests_service(session).create(
        own.user_id,
        own.house_id,
        socket,
    )
    assert dangerous.request.group_id == group_id
    viewer = _viewer(own, own.user_id, is_demo=False)
    service = admin_requests_service(session)

    page = await list_org_requests(viewer, service, grouped=True)
    dangerous.request.status = RequestStatus.DONE
    await session.flush()
    done = await list_org_requests(viewer, service, grouped=True)

    assert [(item.id, item.danger) for item in page.items] == [
        (members[0].id, DangerKind.FLOOD_ELECTRIC),
        (lone.id, None),
    ]
    assert [item.id for item in done.items] == [lone.id, members[0].id]


async def test_a_gji_pdf_of_someone_elses_request_is_not_found(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    neighbour = await add_user(session)
    await add_resident(session, neighbour, own.house_id, None)
    await _open_dialog(session, neighbour)
    request = await _complain(session, own.user_id, own.house_id)

    with pytest.raises(EntityNotFound):
        await requests_service(session, publisher).send_gji_pdf(
            neighbour,
            request.id,
            request.deadline_at + timedelta(hours=1),
        )

    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_GJI_PDF) == []
    assert await events_of(session, EventType.REQUEST_EXPORTED) == []


@pytest.mark.parametrize(
    ("status", "late"),
    [
        (RequestStatus.IN_PROGRESS, timedelta(minutes=-1)),
        (RequestStatus.ON_REVIEW, timedelta(hours=1)),
        (RequestStatus.DONE, timedelta(hours=1)),
    ],
)
async def test_a_gji_pdf_is_refused_before_the_deadline_or_after_the_work(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
    status: RequestStatus,
    late: timedelta,
) -> None:
    await _open_dialog(session, own.user_id)
    request = await _complain(session, own.user_id, own.house_id)
    request.status = status
    await session.flush()

    with pytest.raises(InvalidState):
        await requests_service(session, publisher).send_gji_pdf(
            own.user_id,
            request.id,
            request.deadline_at + late,
        )

    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_GJI_PDF) == []


async def test_a_gji_pdf_of_an_overdue_request_goes_to_its_author(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    await _open_dialog(session, own.user_id)
    request = await _complain(session, own.user_id, own.house_id)

    await requests_service(session, publisher).send_gji_pdf(
        own.user_id,
        request.id,
        request.deadline_at + timedelta(minutes=1),
    )

    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_GJI_PDF) == [
        {"user_id": own.user_id, "request_id": request.id},
    ]
    [event] = await events_of(session, EventType.REQUEST_EXPORTED)
    assert event.payload == {"request_id": request.id, "format": "gji_pdf"}


@pytest.mark.parametrize("stopped", [False, True])
async def test_a_gji_pdf_is_refused_when_the_bot_cannot_write_to_the_author(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
    stopped: bool,
) -> None:
    if stopped:
        user = await _open_dialog(session, own.user_id)
        user.bot_stopped_at = datetime.now(UTC)
        await session.flush()
    request = await _complain(session, own.user_id, own.house_id)

    with pytest.raises(InvalidState, match="Бот не может вам написать"):
        await requests_service(session, publisher).send_gji_pdf(
            own.user_id,
            request.id,
            request.deadline_at + timedelta(minutes=1),
        )

    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_GJI_PDF) == []


async def _open_dialog(session: AsyncSession, user_id: UserId) -> User:
    user = await UsersRepo(session).get_by_id(user_id)
    assert user is not None
    user.max_chat_id = MaxChatId(user.max_user_id)
    await session.flush()
    return user


@pytest.mark.parametrize("is_demo", [False, True])
async def test_a_gji_pdf_says_demo_on_every_page_only_for_a_demo_org(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    publisher: TaskPublisher,
    monkeypatch: pytest.MonkeyPatch,
    is_demo: bool,
) -> None:
    org = await OrgsRepo(session).get(own.org_id)
    assert org is not None
    org.is_demo = is_demo
    await session.flush()
    request = await _complain(session, own.user_id, own.house_id)
    card = await requests_service(session, publisher).get_card(
        own.user_id,
        request.id,
    )
    drawn: list[str] = []
    monkeypatch.setattr(PdfDocument, "text", lambda *args: drawn.append(args[-1]))

    complaint = GjiComplaint(card, request.deadline_at + timedelta(hours=1))
    complaint.render()

    assert complaint.pages_count > 1
    assert drawn == (["ДЕМО"] * complaint.pages_count if is_demo else [])
