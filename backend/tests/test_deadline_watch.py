from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    OrgHouseFlatUser,
    RecordingBroker,
    add_resident,
    add_user,
    admin_requests_service,
    requests_service,
)

from zheka.api.schemas.requests import RequestCard
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import (
    OrgRole,
    RequestCategory,
    RequestChannel,
    RequestPlace,
    RequestStatus,
    ResidentStatus,
)
from zheka.core.errors import EntityNotFound
from zheka.core.ids import HouseId, OrgId, RequestId, UserId
from zheka.core.models import House, Request
from zheka.core.services.requests import RequestDraft
from zheka.core.texts import (
    COMPLAINT_BUTTON,
    REQUEST_PLACE_LINES,
    deadline_lines,
    request_overdue_author,
)
from zheka.infra.database.models import OrgMember
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo


async def _member(session: AsyncSession, org_id: OrgId, role: OrgRole) -> UserId:
    user_id = await add_user(session, "Сотрудник")
    session.add(OrgMember(org_id=org_id, user_id=user_id, role=role))
    await session.flush()
    return user_id


async def _file(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    category: RequestCategory = RequestCategory.LEAK,
    publisher: TaskPublisher | None = None,
) -> Request:
    card = await requests_service(session, publisher).create(
        own.user_id,
        own.house_id,
        RequestDraft(
            category=category,
            description="Течет стояк",
            place=RequestPlace.FLAT,
        ),
    )
    return card.request


async def _demo(session: AsyncSession, org_id: OrgId) -> None:
    org = await OrgsRepo(session).get(org_id)
    assert org is not None
    org.is_demo = True
    await session.flush()


def _texts(broker: RecordingBroker, task: TaskName) -> list[dict[str, Any]]:
    return [
        message
        for message in broker.enqueued(task)
        if "осталось" in message["text"] or "🔴" in message["text"]
    ]


def test_the_warning_is_a_quarter_of_the_term_within_one_and_24_hours() -> None:
    created = datetime(2026, 9, 1, tzinfo=UTC)

    def lead(hours: int) -> timedelta:
        deadline = created + timedelta(hours=hours)
        request = Request(
            created_at=created,
            deadline_at=deadline,
            house_id=HouseId(1),
            category=RequestCategory.LEAK,
            description="",
            status=RequestStatus.NEW,
            channel=RequestChannel.MINIAPP,
        )
        return deadline - request.warn_at

    assert lead(72) == timedelta(hours=18)
    assert lead(4) == timedelta(hours=1)
    assert lead(16) == timedelta(hours=4)
    assert lead(200) == timedelta(hours=24)
    assert lead(2) == timedelta(hours=1)


async def test_the_warning_and_the_overdue_notice_go_once_each(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    chairman = await add_user(session, "Председатель")
    await add_resident(session, chairman, own.house_id, None, is_chairman=True)
    request = await _file(session, own)
    service = requests_service(session, publisher)
    warn = request.deadline_at - timedelta(hours=18)

    assert await service.watch_deadlines(warn - timedelta(minutes=1)) == 0
    assert await service.watch_deadlines(warn + timedelta(minutes=1)) == 1
    assert await service.watch_deadlines(warn + timedelta(minutes=2)) == 0
    assert request.deadline_warned_at == warn + timedelta(minutes=1)
    assert request.overdue_notified_at is None
    await publisher.flush()
    [warning] = _texts(broker, TaskName.BROADCAST_TO_USERS)
    assert warning["user_ids"] == [staff]
    assert f"Заявке №{request.id}" in warning["text"]
    assert "осталось 18 ч" in warning["text"]
    assert _texts(broker, TaskName.SEND_TO_USER) == []

    late = request.deadline_at + timedelta(minutes=1)
    assert await service.watch_deadlines(late) == 1
    assert await service.watch_deadlines(late) == 0
    assert request.overdue_notified_at == late
    assert request.deadline_warned_at == warn + timedelta(minutes=1)
    await publisher.flush()
    [_, overdue] = _texts(broker, TaskName.BROADCAST_TO_USERS)
    assert overdue["user_ids"] == [staff]
    assert "просрочена" in overdue["text"]
    assert REQUEST_PLACE_LINES[RequestPlace.FLAT] in overdue["text"]
    author, chair = _texts(broker, TaskName.SEND_TO_USER)
    assert author["user_id"] == own.user_id
    assert author["mandatory"] is True
    assert author["app_button"] == COMPLAINT_BUTTON
    assert author["app_path"] == f"/requests/{request.id}"
    assert "ПП РФ № 416, п. 13" in author["text"]
    assert chair["user_id"] == chairman
    assert chair["text"].startswith("🔴 В доме просрочена заявка")


async def test_after_downtime_only_the_overdue_notice_goes(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    await _member(session, own.org_id, OrgRole.EMPLOYEE)
    request = await _file(session, own, RequestCategory.WATER_SUPPLY)
    service = requests_service(session, publisher)
    late = request.deadline_at + timedelta(hours=5)

    assert await service.watch_deadlines(late) == 1

    assert request.deadline_warned_at == late
    assert request.overdue_notified_at == late
    await publisher.flush()
    [staff] = _texts(broker, TaskName.BROADCAST_TO_USERS)
    assert "просрочена" in staff["text"]
    sent = [
        *_texts(broker, TaskName.BROADCAST_TO_USERS),
        *_texts(broker, TaskName.SEND_TO_USER),
    ]
    assert all("осталось" not in message["text"] for message in sent)


async def test_the_database_picks_the_warning_moment_by_the_term(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _file(session, own, RequestCategory.WATER_SUPPLY)
    repo = RequestsRepo(session)
    warn = request.deadline_at - timedelta(hours=1)

    assert await repo.list_deadline_due(warn - timedelta(minutes=1)) == []
    assert await repo.list_deadline_due(warn) == [request]


async def test_requests_on_review_or_done_are_not_watched(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    review = await _file(session, own)
    done = await _file(session, own)
    review.status = RequestStatus.ON_REVIEW
    done.status = RequestStatus.DONE
    await session.flush()

    late = review.deadline_at + timedelta(days=1)
    assert await requests_service(session).watch_deadlines(late) == 0


async def test_the_executor_hears_only_while_an_executor_of_the_org(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    stranger = await add_user(session, "Бывший исполнитель")
    promoted = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    served = await _file(session, own)
    orphaned = await _file(session, own)
    staffed = await _file(session, own)
    served.executor_user_id = executor
    orphaned.executor_user_id = stranger
    staffed.executor_user_id = promoted
    await session.flush()

    late = served.deadline_at + timedelta(minutes=1)
    assert await requests_service(session, publisher).watch_deadlines(late) == 3

    await publisher.flush()
    recipients = [sent["user_id"] for sent in _texts(broker, TaskName.SEND_TO_USER)]
    assert executor in recipients
    assert stranger not in recipients
    assert promoted not in recipients


async def test_a_blocked_chairman_hears_nothing(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    chairman = await add_user(session, "Председатель")
    await add_resident(
        session,
        chairman,
        own.house_id,
        None,
        is_chairman=True,
        status=ResidentStatus.BLOCKED,
    )
    request = await _file(session, own)

    late = request.deadline_at + timedelta(minutes=1)
    await requests_service(session, publisher).watch_deadlines(late)

    await publisher.flush()
    recipients = [sent["user_id"] for sent in _texts(broker, TaskName.SEND_TO_USER)]
    assert recipients == [own.user_id]


async def test_the_demo_button_expires_the_deadline_and_notifies_at_once(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    await _demo(session, own.org_id)
    service = requests_service(session, publisher)
    request = await _file(session, own)
    before = await service.get_card(own.user_id, request.id)
    assert RequestCard.of(before, [], []).can_demo_expire is True
    now = datetime.now(UTC)

    card = await service.demo_expire(own.user_id, request.id, now)

    moment = now - timedelta(minutes=1)
    assert card.request.deadline_at == moment
    assert card.request.react_deadline_at == moment
    assert card.request.overdue_notified_at == now
    assert card.can_demo_expire is False
    assert await service.watch_deadlines(now + timedelta(minutes=5)) == 0
    await publisher.flush()
    [overdue] = _texts(broker, TaskName.BROADCAST_TO_USERS)
    assert overdue["user_ids"] == [staff]
    [author] = _texts(broker, TaskName.SEND_TO_USER)
    assert author["user_id"] == own.user_id
    assert author["app_button"] == COMPLAINT_BUTTON


async def test_the_demo_button_is_only_in_a_demo_org(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    request = await _file(session, own)

    card = await service.get_card(own.user_id, request.id)
    assert card.can_demo_expire is False
    with pytest.raises(EntityNotFound):
        await service.demo_expire(own.user_id, request.id, datetime.now(UTC))


async def test_the_demo_button_is_only_for_the_author(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    stranger = await add_user(session, "Сосед")
    await add_resident(session, stranger, own.house_id, None)
    request = await _file(session, own)

    with pytest.raises(EntityNotFound):
        await requests_service(session).demo_expire(
            stranger,
            request.id,
            datetime.now(UTC),
        )


async def test_the_demo_button_skips_an_overdue_request(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    service = requests_service(session)
    request = await _file(session, own)
    late = request.deadline_at + timedelta(minutes=1)

    with pytest.raises(EntityNotFound):
        await service.demo_expire(own.user_id, request.id, late)


async def test_the_demo_button_skips_a_request_on_review(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    service = requests_service(session)
    request = await _file(session, own)
    request.status = RequestStatus.ON_REVIEW
    await session.flush()

    assert (await service.get_card(own.user_id, request.id)).can_demo_expire is False
    with pytest.raises(EntityNotFound):
        await service.demo_expire(own.user_id, request.id, datetime.now(UTC))


async def test_the_staff_card_has_no_demo_button(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    request = await _file(session, own)

    staff_card = await admin_requests_service(session).card(own.org_id, request.id)

    assert staff_card.card.can_demo_expire is False


async def test_an_author_who_is_the_chairman_and_the_executor_hears_once(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    [resident] = await ResidentsRepo(session).list_for_user(own.user_id)
    resident.is_chairman = True
    session.add(
        OrgMember(org_id=own.org_id, user_id=own.user_id, role=OrgRole.EXECUTOR),
    )
    request = await _file(session, own)
    request.executor_user_id = own.user_id
    await session.flush()

    late = request.deadline_at + timedelta(minutes=1)
    await requests_service(session, publisher).watch_deadlines(late)

    await publisher.flush()
    [author] = _texts(broker, TaskName.SEND_TO_USER)
    assert author["user_id"] == own.user_id
    assert author["app_button"] == COMPLAINT_BUTTON


@pytest.mark.parametrize(
    ("term", "lead"),
    [
        (timedelta(days=8), timedelta(hours=24)),
        (timedelta(hours=2), timedelta(hours=1)),
    ],
)
async def test_the_database_clamps_the_warning_to_one_to_24_hours(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    term: timedelta,
    lead: timedelta,
) -> None:
    request = await _file(session, own)
    request.deadline_at = request.created_at + term
    await session.flush()
    repo = RequestsRepo(session)
    warn = request.deadline_at - lead

    assert await repo.list_deadline_due(warn - timedelta(minutes=1)) == []
    assert await repo.list_deadline_due(warn) == [request]


async def test_the_demo_button_keeps_a_missing_react_deadline(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    service = requests_service(session)
    request = await _file(session, own, RequestCategory.YARD)
    now = datetime.now(UTC)

    card = await service.demo_expire(own.user_id, request.id, now)

    assert card.request.deadline_at == now - timedelta(minutes=1)
    assert card.request.react_deadline_at is None


@pytest.mark.parametrize(
    ("category", "basis"),
    [
        (
            RequestCategory.LEAK,
            (
                "📜 ПП РФ № 416, п. 13: локализовать аварию - за 30 минут с "
                "регистрации заявки, устранить - не более 3 суток с даты аварии"
            ),
        ),
        (RequestCategory.ELEVATOR, None),
    ],
    ids=["norm", "no-norm"],
)
def test_the_basis_line_goes_only_with_a_norm(
    category: RequestCategory,
    basis: str | None,
) -> None:
    request = Request(
        id=RequestId(7),
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        deadline_at=datetime(2026, 9, 2, tzinfo=UTC),
        house_id=HouseId(1),
        category=category,
        description="",
        status=RequestStatus.IN_PROGRESS,
        channel=RequestChannel.MINIAPP,
    )
    house = House(
        region="Москва",
        city="Москва",
        street="ул. Тверская",
        building="д. 1",
        chat_binding_code="code",
        timezone="Europe/Moscow",
    )

    for text in (deadline_lines(request, house), request_overdue_author(request)):
        lines = text.split("\n")
        assert [line for line in lines if line.startswith("📜")] == (
            [basis] if basis else []
        )
