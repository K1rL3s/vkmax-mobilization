from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from maxo.utils.webapp import WebAppChat, WebAppInitData, WebAppUser
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    StubClassifier,
    add_resident,
    add_user,
    admin_requests_service,
    events_of,
    make_config,
    photo_name,
    requests_service,
)

from zheka.api.dependencies.current_account import CurrentAccount
from zheka.api.dependencies.current_org import CurrentOrg
from zheka.api.dependencies.current_user import API_CHECKER
from zheka.api.routes.requests import (
    PP290,
    cancel_request,
    classify_request_text,
    export_request,
    get_pp290,
)
from zheka.api.schemas.requests import (
    AdminRequestCard,
    CancelRequestRequest,
    ClassifyRequestRequest,
    CreateRequestRequest,
    HouseProblemsResponse,
    OpenProblemItem,
    Pp290Catalog,
    RequestCard,
    ResolvedProblemItem,
)
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import (
    CATEGORY_RULES,
    CancelReason,
    DangerKind,
    EventType,
    OrgRole,
    RequestActorRole,
    RequestAttachmentKind,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestGroupStatus,
    RequestPlace,
    RequestStatus,
    ResidentRole,
    ResidentStatus,
    ResponsibilityZone,
)
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
    ZhekaError,
)
from zheka.core.ids import (
    FlatId,
    HouseId,
    OrgId,
    RequestGroupId,
    RequestId,
    UserId,
)
from zheka.core.services.files import FilesService
from zheka.core.services.houses import NOT_CONNECTED
from zheka.core.services.requests import (
    AUTO_CLOSE_AFTER,
    MAX_ATTACHMENTS,
    REJECTION_PHOTO_REQUIRED,
    RequestDraft,
)
from zheka.core.texts import REQUEST_EXPORT_DISCLAIMER
from zheka.infra.database.models import (
    Flat,
    OrgMember,
    Request,
    RequestGroup,
    RequestStatusLog,
    Resident,
)
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.tables.requests import (
    request_status_log_table,
    requests_table,
)
from zheka.infra.yandex import YandexQuota
from zheka.infra.yandex.quota import QUOTA_CALLS, QUOTA_WINDOW_SECONDS

DESCRIPTION = "Течет труба в ванной, вода на полу"


async def _member(session: AsyncSession, org_id: OrgId, role: OrgRole) -> UserId:
    user_id = await add_user(session, "Сотрудник")
    session.add(OrgMember(org_id=org_id, user_id=user_id, role=role))
    await session.flush()
    return user_id


def _draft(
    *,
    category: RequestCategory = RequestCategory.LEAK,
    description: str = DESCRIPTION,
    flat_id: FlatId | None = None,
    attachments: Sequence[str] = (),
    group_id: RequestGroupId | None = None,
    place: RequestPlace | None = RequestPlace.FLAT,
) -> RequestDraft:
    return RequestDraft(
        category=category,
        description=description,
        flat_id=flat_id,
        attachments=attachments,
        group_id=group_id,
        place=place,
    )


async def _neighbour(session: AsyncSession, house_id: HouseId, number: str) -> UserId:
    user_id = await add_user(session, f"Сосед {number}")
    flat = Flat(house_id=house_id, number=number)
    session.add(flat)
    await session.flush()
    session.add(
        Resident(
            user_id=user_id,
            house_id=house_id,
            flat_id=flat.id,
            role=ResidentRole.OWNER,
        ),
    )
    await session.flush()
    return user_id


async def _complain(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    category: RequestCategory = RequestCategory.LEAK,
) -> Request:
    card = await requests_service(session).create(
        user_id,
        house_id,
        RequestDraft(
            category=category,
            description="Течет стояк",
            place=RequestPlace.FLAT,
        ),
    )
    return card.request


async def _group_of_three(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> tuple[list[Request], RequestGroupId]:
    members = [
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
        )
        for number in ("11", "12", "13")
    ]
    group_id = members[-1].group_id
    assert group_id is not None
    return members, group_id


async def _age(session: AsyncSession, request_id: RequestId, hours: int) -> None:
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(
            created_at=requests_table.c.created_at - timedelta(hours=hours),
            deadline_at=requests_table.c.deadline_at - timedelta(hours=hours),
        )
    )
    await session.execute(stmt)
    await session.flush()


async def _block(session: AsyncSession, user_id: UserId, house_id: HouseId) -> None:
    residents_repo = ResidentsRepo(session)
    resident = await residents_repo.get_for_house(user_id, house_id)
    assert resident is not None
    await residents_repo.set_status(resident, ResidentStatus.BLOCKED, "Задолженность")


async def _add_group(
    session: AsyncSession,
    house_id: HouseId,
    category: RequestCategory = RequestCategory.LEAK,
    status: RequestGroupStatus = RequestGroupStatus.OPEN,
) -> RequestGroupId:
    group = RequestGroup(
        house_id=house_id,
        category=category,
        window_started_at=datetime.now(UTC),
        status=status,
    )
    session.add(group)
    await session.flush()
    return group.id


async def _mark_done(session: AsyncSession, request_id: RequestId) -> None:
    request = await RequestsRepo(session).get(request_id)
    assert request is not None
    request.status = RequestStatus.DONE
    request.completion_reason = RequestCompletionReason.RESIDENT_ACCEPTED
    request.done_at = datetime.now(UTC)
    await session.flush()


async def _mark_on_review(session: AsyncSession, request_id: RequestId) -> Request:
    request = await RequestsRepo(session).get(request_id)
    assert request is not None
    request.status = RequestStatus.ON_REVIEW
    request.reviewed_at = datetime.now(UTC)
    await session.flush()
    return request


async def _logs(session: AsyncSession, request_id: RequestId) -> list[RequestStatusLog]:
    stmt = select(RequestStatusLog).where(
        request_status_log_table.c.request_id == request_id,
    )
    return list((await session.execute(stmt)).scalars().all())


def _account(user_id: UserId) -> CurrentAccount:
    return CurrentAccount(user_id=user_id, consent_at=datetime.now(UTC))


async def test_create_writes_the_request_its_photos_the_log_and_the_event(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    names = [photo_name(), photo_name()]

    card = await requests_service(session).create(
        own.user_id,
        own.house_id,
        _draft(flat_id=own.flat_id, attachments=names),
    )

    request_id = card.request.id
    assert card.request.status is RequestStatus.NEW
    assert card.request.channel is RequestChannel.MINIAPP
    assert card.request.flat_id == own.flat_id
    assert card.request.is_staff_author is False
    assert [photo.path for photo in card.issue_attachments] == names
    [log] = await _logs(session, request_id)
    assert log.from_status is None
    assert log.to_status is RequestStatus.NEW
    assert log.by_role == RequestActorRole.RESIDENT
    assert log.by_user_id == own.user_id
    [event] = await events_of(session, EventType.REQUEST_CREATED)
    assert event.payload["has_attachments"] is True
    assert event.payload["is_repeat"] is False
    assert event.payload["category"] == RequestCategory.LEAK.value


async def test_create_refuses_a_stranger(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    stranger = await add_user(session)

    with pytest.raises(EntityNotFound):
        await requests_service(session).create(stranger, own.house_id, _draft())


async def test_create_refuses_a_blocked_resident(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights):
        await requests_service(session).create(own.user_id, own.house_id, _draft())


async def test_create_refuses_a_flat_that_is_not_the_authors(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    neighbour_flat = Flat(house_id=own.house_id, number="2")
    session.add(neighbour_flat)
    await session.flush()

    with pytest.raises(EntityNotFound):
        await requests_service(session).create(
            own.user_id,
            own.house_id,
            _draft(flat_id=neighbour_flat.id),
        )


@pytest.mark.parametrize(
    ("draft", "error"),
    [
        (
            _draft(attachments=[photo_name() for _ in range(MAX_ATTACHMENTS + 1)]),
            InvalidRequest,
        ),
        (_draft(attachments=["../../etc/passwd"]), EntityNotFound),
        (_draft(attachments=[photo_name().replace(".jpg", ".pdf")]), EntityNotFound),
        (_draft(description="   "), InvalidRequest),
    ],
)
async def test_create_refuses_a_bad_draft(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    draft: RequestDraft,
    error: type[ZhekaError],
) -> None:

    with pytest.raises(error):
        await requests_service(session).create(own.user_id, own.house_id, draft)


async def test_create_marks_a_request_written_by_staff_of_the_same_org(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(
        resident_role=ResidentRole.OWNER,
        org_role=OrgRole.EMPLOYEE,
    )

    card = await requests_service(session).create(
        own.user_id,
        own.house_id,
        _draft(),
    )

    assert card.request.is_staff_author is True


async def test_create_joins_an_open_group_of_the_same_house_and_category(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    group_id = await _add_group(session, own.house_id)
    service = requests_service(session)

    first = await service.create(own.user_id, own.house_id, _draft(group_id=group_id))
    neighbour = await _neighbour(session, own.house_id, "2")
    second = await service.create(neighbour, own.house_id, _draft(group_id=group_id))

    assert first.request.group_id == group_id
    assert second.group_size == 2
    assert RequestCard.of(second, [], []).group_id == group_id


@pytest.mark.parametrize(
    ("foreign", "category", "status", "error"),
    [
        (True, RequestCategory.LEAK, RequestGroupStatus.OPEN, EntityNotFound),
        (False, RequestCategory.ELEVATOR, RequestGroupStatus.OPEN, InvalidRequest),
        (False, RequestCategory.LEAK, RequestGroupStatus.CLOSED, InvalidState),
    ],
)
async def test_create_refuses_a_group_that_does_not_fit(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
    foreign: bool,
    category: RequestCategory,
    status: RequestGroupStatus,
    error: type[ZhekaError],
) -> None:
    house = await make_org_house_flat_user() if foreign else own
    group_id = await _add_group(session, house.house_id, category, status)

    with pytest.raises(error):
        await requests_service(session).create(
            own.user_id,
            own.house_id,
            _draft(group_id=group_id),
        )


async def test_card_takes_the_current_house_org_and_the_category_hours(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    other = await make_org_house_flat_user()
    service = requests_service(session)
    created = await service.create(
        own.user_id,
        own.house_id,
        _draft(category=RequestCategory.ELEVATOR),
    )
    house = await HousesRepo(session).get(own.house_id)
    org = await OrgsRepo(session).get(other.org_id)
    assert house is not None
    assert org is not None
    house.org_id = other.org_id
    await session.flush()

    card = RequestCard.of(
        await service.get_card(own.user_id, created.request.id),
        [],
        [],
    )

    assert card.org_name == org.name
    assert (card.deadline_text, card.deadline_basis) == ("24 часа", None)
    admin_card = AdminRequestCard.of_admin(
        await admin_requests_service(session).card(other.org_id, created.request.id),
        [],
        [],
        CurrentOrg(
            org_id=other.org_id,
            user_id=other.user_id,
            role=OrgRole.ADMIN,
            is_demo=False,
        ),
    )
    assert (admin_card.org_name, admin_card.deadline_text) == (org.name, "24 часа")
    house.org_id = None
    await session.flush()
    orphan = await service.get_card(own.user_id, created.request.id)
    assert RequestCard.of(orphan, [], []).org_name is None


async def test_list_mine_shows_own_requests_of_the_current_house_by_status(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    other_house = await make_org_house_flat_user()
    session.add(
        Resident(
            user_id=own.user_id,
            house_id=other_house.house_id,
            role=ResidentRole.OWNER,
        ),
    )
    await session.flush()
    neighbour = await _neighbour(session, own.house_id, "2")
    service = requests_service(session)

    done = await service.create(
        own.user_id,
        own.house_id,
        _draft(attachments=[photo_name()]),
    )
    fresh = await service.create(own.user_id, own.house_id, _draft())
    await service.create(own.user_id, other_house.house_id, _draft())
    await service.create(neighbour, own.house_id, _draft())
    await _mark_done(session, done.request.id)

    rows, total = await service.list_mine(own.user_id, own.house_id, None, 20, 0)
    done_rows, done_total = await service.list_mine(
        own.user_id,
        own.house_id,
        RequestStatus.DONE,
        20,
        0,
    )

    assert total == 2
    assert [(row.request.id, row.has_attachments) for row in rows] == [
        (fresh.request.id, False),
        (done.request.id, True),
    ]
    assert done_total == 1
    assert [row.request.id for row in done_rows] == [done.request.id]


async def test_accept_closes_the_reviewed_request_and_opens_rating(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = created.request.id
    await _mark_on_review(session, request_id)

    accepted = await service.accept(own.user_id, request_id)

    assert accepted.request.status is RequestStatus.DONE
    assert (
        accepted.request.completion_reason is RequestCompletionReason.RESIDENT_ACCEPTED
    )
    assert accepted.request.done_at is not None
    assert accepted.can_review is False
    assert accepted.can_rate is True
    assert (
        RequestCard.of(accepted, [], []).completion_reason
        is RequestCompletionReason.RESIDENT_ACCEPTED
    )
    logs = await _logs(session, request_id)
    assert logs[-1].from_status is RequestStatus.ON_REVIEW
    assert logs[-1].to_status is RequestStatus.DONE
    assert logs[-1].by_role == RequestActorRole.RESIDENT
    [reviewed] = await events_of(session, EventType.REQUEST_REVIEWED)
    assert reviewed.payload == {"request_id": request_id, "accepted": True}
    [changed] = await events_of(session, EventType.REQUEST_STATUS_CHANGED)
    assert changed.user_id == own.user_id
    assert changed.payload == {
        "request_id": request_id,
        "from": RequestStatus.ON_REVIEW.value,
        "to": RequestStatus.DONE.value,
        "by_role": RequestActorRole.RESIDENT.value,
    }


async def test_accept_refuses_a_request_outside_review(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())

    with pytest.raises(InvalidState, match="на приемке"):
        await service.accept(own.user_id, created.request.id)


async def test_auto_close_ends_an_expired_review_once_and_tells_the_author(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    service = requests_service(session, publisher)
    now = datetime.now(UTC)
    ids = []
    for age in (AUTO_CLOSE_AFTER, timedelta(hours=47)):
        created = await service.create(own.user_id, own.house_id, _draft())
        request = await _mark_on_review(session, created.request.id)
        request.reviewed_at = now - age
        ids.append(created.request.id)
    await session.flush()
    stale, fresh = ids

    reviewing = await service.get_card(own.user_id, stale)
    assert RequestCard.of(reviewing, [], []).auto_close_at == now

    assert await service.auto_close(now) == 1
    assert await service.auto_close(now) == 0

    closed = await service.get_card(own.user_id, stale)
    assert closed.request.status is RequestStatus.DONE
    assert closed.request.completion_reason is RequestCompletionReason.AUTO_CLOSED
    assert closed.can_rate is False
    assert closed.auto_close_at is None
    assert (await service.get_card(own.user_id, fresh)).request.status is (
        RequestStatus.ON_REVIEW
    )
    logs = await _logs(session, stale)
    assert logs[-1].by_user_id is None
    assert logs[-1].by_role == RequestActorRole.SYSTEM
    [event] = await events_of(session, EventType.REQUEST_AUTO_CLOSED)
    assert event.payload == {"request_id": stale}
    assert await events_of(session, EventType.REQUEST_REVIEWED) == []
    [changed] = await events_of(session, EventType.REQUEST_STATUS_CHANGED)
    assert changed.user_id is None
    assert changed.payload["by_role"] == RequestActorRole.SYSTEM.value
    await publisher.flush()
    [sent] = broker.enqueued(TaskName.SEND_TO_USER)
    assert sent["user_id"] == own.user_id
    assert sent["mandatory"] is True
    assert f"№{stale}" in sent["text"]


async def test_rate_puts_the_one_score_and_closes_the_rating(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = created.request.id
    await _mark_done(session, request_id)

    rated = await service.rate(own.user_id, request_id, 4, "  Спасибо  ")

    assert rated.request.rating == 4
    assert rated.request.feedback == "Спасибо"
    assert rated.can_rate is False
    events = await events_of(session, EventType.REQUEST_RATED)
    assert events[0].payload["score"] == 4
    assert events[0].payload["has_comment"] is True
    with pytest.raises(InvalidState):
        await service.rate(own.user_id, request_id, 1, None)


async def test_rate_refuses_a_request_that_is_not_done(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    card = await service.create(own.user_id, own.house_id, _draft())

    with pytest.raises(InvalidState):
        await service.rate(own.user_id, card.request.id, 5, None)


@pytest.mark.parametrize("rating", [0, 6])
async def test_rate_refuses_a_score_outside_the_scale(
    session: AsyncSession,
    rating: int,
) -> None:
    with pytest.raises(InvalidRequest):
        await requests_service(session).rate(UserId(1), RequestId(1), rating, None)


async def test_repeat_refuses_a_parent_that_is_not_done(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())

    with pytest.raises(InvalidState):
        await service.repeat(own.user_id, created.request.id, None, [])


async def test_repeat_from_review_rejects_the_result_and_opens_a_new_request(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    parent_id = created.request.id
    await _mark_on_review(session, parent_id)

    proof = photo_name()

    repeated = await service.repeat(
        own.user_id,
        parent_id,
        "Не устранили протечку под ванной",
        [proof],
        channel=RequestChannel.BOT,
    )

    assert [photo.path for photo in repeated.issue_attachments] == [proof]
    parent = await service.get_card(own.user_id, parent_id)
    assert parent.request.status is RequestStatus.DONE
    assert parent.request.completion_reason is RequestCompletionReason.RESIDENT_REJECTED
    assert parent.can_rate is False
    assert repeated.request.parent_request_id == parent_id
    assert repeated.request.status is RequestStatus.NEW
    assert repeated.request.description == "Не устранили протечку под ванной"
    assert repeated.request.channel is RequestChannel.BOT
    logs = await _logs(session, parent_id)
    assert logs[-1].from_status is RequestStatus.ON_REVIEW
    assert logs[-1].to_status is RequestStatus.DONE
    assert logs[-1].by_role == RequestActorRole.RESIDENT
    reviewed = await events_of(session, EventType.REQUEST_REVIEWED)
    assert reviewed[0].payload == {"request_id": parent_id, "accepted": False}
    created_events = await events_of(session, EventType.REQUEST_CREATED)
    assert created_events[-1].payload["channel"] == RequestChannel.BOT.value


async def test_repeat_from_review_requires_a_comment(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = created.request.id
    await _mark_on_review(session, request_id)

    with pytest.raises(InvalidRequest, match="что сделано плохо"):
        await service.repeat(own.user_id, request_id, None, [])

    request = await RequestsRepo(session).get(request_id)
    assert request is not None
    assert request.status is RequestStatus.ON_REVIEW


async def test_repeat_copies_the_parent_and_starts_from_scratch(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(
        own.user_id,
        own.house_id,
        _draft(flat_id=own.flat_id, attachments=[photo_name()]),
    )
    parent_id = created.request.id
    await _mark_done(session, parent_id)

    repeated = await service.repeat(
        own.user_id,
        parent_id,
        "Течет снова, хуже прежнего",
        [photo_name()],
    )

    assert repeated.request.parent_request_id == parent_id
    assert repeated.request.status is RequestStatus.NEW
    assert repeated.request.category is RequestCategory.LEAK
    assert repeated.request.flat_id == own.flat_id
    assert repeated.request.description == "Течет снова, хуже прежнего"
    assert len(repeated.issue_attachments) == 1
    events = await events_of(session, EventType.REQUEST_CREATED)
    assert [event.payload["is_repeat"] for event in events] == [False, True]
    again = await service.repeat(own.user_id, parent_id, None, [])
    assert again.request.description == DESCRIPTION
    with pytest.raises(InvalidRequest):
        await service.repeat(own.user_id, parent_id, "   ", [])


async def test_repeat_refuses_a_blocked_resident(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    parent_id = created.request.id
    await _mark_done(session, parent_id)
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights):
        await service.repeat(own.user_id, parent_id, "Опять течет", [])


async def test_export_prints_the_whole_life_of_the_request(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    service = requests_service(session)
    admin = admin_requests_service(session)
    issue = photo_name()
    result = photo_name()
    created = await service.create(
        own.user_id,
        own.house_id,
        _draft(attachments=[issue]),
    )
    request_id = created.request.id
    await admin.reply(own.org_id, request_id, "Сантехник будет завтра", staff)
    for target in (
        RequestStatus.ACCEPTED,
        RequestStatus.IN_PROGRESS,
        RequestStatus.ON_REVIEW,
    ):
        await admin.change_status(own.org_id, request_id, target, None, staff)
    await RequestsRepo(session).add_attachment(
        request_id,
        result,
        RequestAttachmentKind.RESULT,
        staff,
    )
    await service.accept(own.user_id, request_id)
    await service.rate(own.user_id, request_id, 4, "Быстро, но натоптали")

    export = await export_request(
        request_id,
        _account(own.user_id),
        service,
        FilesService(make_config().files, "test-token"),
    )

    card = export.request
    assert export.disclaimer == REQUEST_EXPORT_DISCLAIMER
    assert card.id == request_id
    assert [message.text for message in card.messages] == ["Сантехник будет завтра"]
    assert [(row.to_status, row.by_role) for row in card.timeline] == [
        (RequestStatus.NEW, RequestActorRole.RESIDENT),
        (RequestStatus.ACCEPTED, RequestActorRole.STAFF),
        (RequestStatus.IN_PROGRESS, RequestActorRole.STAFF),
        (RequestStatus.ON_REVIEW, RequestActorRole.STAFF),
        (RequestStatus.DONE, RequestActorRole.RESIDENT),
    ]
    assert card.rating == 4
    assert card.feedback == "Быстро, но натоптали"
    assert [photo.name for photo in card.photos] == [issue]
    assert [photo.name for photo in card.result_photos] == [result]
    assert all("sig=" in photo.url for photo in [*card.photos, *card.result_photos])
    events = await events_of(session, EventType.REQUEST_EXPORTED)
    assert [(event.user_id, event.payload["request_id"]) for event in events] == [
        (own.user_id, request_id),
    ]


async def test_export_hides_a_request_of_another_resident_and_records_nothing(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    neighbour = await _neighbour(session, own.house_id, "2")
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())

    with pytest.raises(EntityNotFound):
        await service.export(neighbour, created.request.id)

    assert await events_of(session, EventType.REQUEST_EXPORTED) == []


@pytest.mark.parametrize("category", [RequestCategory.HEATING, None])
async def test_classify_answers_the_category_with_its_zone_and_records_it(
    session: AsyncSession,
    category: RequestCategory | None,
) -> None:
    user_id = await add_user(session)
    service = requests_service(session, classifier=StubClassifier(category))

    response = await classify_request_text(
        _account(user_id),
        service,
        ClassifyRequestRequest(text="Батареи холодные"),
        YandexQuota(),
    )

    assert response.category is category
    events = await events_of(session, EventType.LLM_SUGGESTED)
    if category is None:
        assert response.zone is None
        assert events == []
    else:
        assert response.zone is CATEGORY_RULES[category].zone
        assert [(event.user_id, event.payload) for event in events] == [
            (user_id, {"category": category.value}),
        ]


@pytest.mark.parametrize(
    ("suggested", "accepted", "recorded"),
    [(True, True, True), (True, False, False), (False, True, False)],
)
async def test_create_records_an_accepted_suggestion_only_when_accepted(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    suggested: bool,
    accepted: bool,
    recorded: bool,
) -> None:

    await requests_service(session).create(
        own.user_id,
        own.house_id,
        RequestDraft(
            category=RequestCategory.ELEVATOR,
            description=DESCRIPTION,
            llm_suggested=suggested,
            llm_accepted=accepted,
        ),
    )

    events = await events_of(session, EventType.LLM_ACCEPTED)
    expected = [(own.user_id, own.house_id, RequestCategory.ELEVATOR.value)]
    assert [
        (event.user_id, event.payload["house_id"], event.payload["category"])
        for event in events
    ] == (expected if recorded else [])


async def test_create_refuses_a_house_whose_org_is_not_connected(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(
        resident_role=ResidentRole.OWNER,
        registered=False,
    )
    service = requests_service(session)

    with pytest.raises(InvalidState, match=NOT_CONNECTED):
        await service.create(own.user_id, own.house_id, _draft())

    _, total = await service.list_mine(own.user_id, own.house_id, None, 20, 0)
    assert total == 0


async def test_a_new_and_a_repeat_request_notify_the_staff_but_not_executors(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    roles = (OrgRole.ADMIN, OrgRole.EMPLOYEE, OrgRole.EXECUTOR)
    staff = {role: await add_user(session) for role in roles}
    session.add_all(
        OrgMember(org_id=own.org_id, user_id=user_id, role=role)
        for role, user_id in staff.items()
    )
    session.add(OrgMember(org_id=own.org_id, user_id=own.user_id, role=OrgRole.ADMIN))
    await session.flush()
    service = requests_service(session, publisher)

    created = await service.create(own.user_id, own.house_id, _draft())
    await _mark_done(session, created.request.id)
    repeated = await service.repeat(own.user_id, created.request.id, None, [])

    await publisher.flush()
    house = await HousesRepo(session).get(own.house_id)
    assert house is not None
    queued = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert [message["app_path"] for message in queued] == [
        f"/admin/requests/{created.request.id}",
        f"/admin/requests/{repeated.request.id}",
    ]
    first = queued[0]
    assert sorted(first["user_ids"]) == sorted(
        [staff[OrgRole.ADMIN], staff[OrgRole.EMPLOYEE]],
    )
    assert first["mandatory"] is False
    assert first["category"] == "requests"
    react = created.request.react_deadline_at
    assert react is not None
    deadline = house.local(created.request.deadline_at)
    assert first["text"] == (
        f"🆕 Заявка №{created.request.id} «💧 Протечка»\n🏢 {house.address}\n"
        "🏠 Личная: в квартире\n"
        f"⏱ Локализовать аварию до {house.local(react):%H:%M %d.%m}\n"
        f"⏰ Срок: до {deadline:%H:%M %d.%m}\n"
        "📜 ПП РФ № 416, п. 13: локализовать аварию - за 30 минут с регистрации "
        "заявки, устранить - не более 3 суток с даты аварии"
    )


async def _close_behind_the_session(
    session: AsyncSession,
    request_id: RequestId,
) -> None:
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(status=RequestStatus.DONE)
    )
    await session.execute(stmt)


async def test_accept_rereads_a_request_closed_meanwhile(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = created.request.id
    await _mark_on_review(session, request_id)
    await _close_behind_the_session(session, request_id)

    with pytest.raises(InvalidState, match="на приемке"):
        await service.accept(own.user_id, request_id)


async def test_repeat_rereads_a_request_closed_meanwhile(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = created.request.id
    await _mark_on_review(session, request_id)
    await _close_behind_the_session(session, request_id)

    await service.repeat(own.user_id, request_id, "Не устранили протечку", [])

    logs = await _logs(session, request_id)
    assert [log.to_status for log in logs] == [RequestStatus.NEW]


async def test_classify_answers_without_the_model_past_the_hourly_quota(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = await add_user(session)
    other_id = await add_user(session)
    classifier = StubClassifier(RequestCategory.HEATING)
    service = requests_service(session, classifier=classifier)
    quota = YandexQuota()
    clock = [0.0]
    monkeypatch.setattr("zheka.infra.quota.monotonic", lambda: clock[0])

    async def ask(who: UserId) -> RequestCategory | None:
        body = ClassifyRequestRequest(text="Батареи холодные")
        response = await classify_request_text(_account(who), service, body, quota)
        return response.category

    answers = [await ask(user_id) for _ in range(QUOTA_CALLS + 1)]
    assert answers[-2:] == [RequestCategory.HEATING, None]
    assert await ask(other_id) is RequestCategory.HEATING
    clock[0] = QUOTA_WINDOW_SECONDS
    assert await ask(user_id) is RequestCategory.HEATING


def test_a_request_description_is_capped() -> None:
    CreateRequestRequest(category=RequestCategory.LEAK, description="я" * 4000)

    with pytest.raises(ValidationError):
        CreateRequestRequest(category=RequestCategory.LEAK, description="я" * 4001)


def test_a_leak_is_accepted_in_half_an_hour_and_fixed_in_three_days() -> None:
    rule = CATEGORY_RULES[RequestCategory.LEAK]
    created = datetime(2026, 9, 28, 20, 10, tzinfo=UTC)

    react, fix = rule.deadlines(created, MOSCOW)

    assert react == created + timedelta(minutes=30)
    assert fix == created + timedelta(days=3)
    assert (rule.react_text, rule.deadline_text, rule.basis) == (
        "30 минут",
        "3 суток",
        (
            "ПП РФ № 416, п. 13: локализовать аварию - за 30 минут с регистрации "
            "заявки, устранить - не более 3 суток с даты аварии"
        ),
    )


@pytest.mark.parametrize(
    ("category", "text", "basis"),
    [
        (
            RequestCategory.WATER_SUPPLY,
            "4 часа",
            (
                "ПП РФ № 354, прил. 1, п. 1, 4: допустимый перерыв - 4 часа подряд "
                "и 8 часов за месяц"
            ),
        ),
        (
            RequestCategory.HEATING,
            "16 часов",
            (
                "ПП РФ № 354, прил. 1, п. 14: допустимый перерыв - 16 часов подряд, "
                "если в квартире не ниже +12 °C, и 24 часа за месяц"
            ),
        ),
        (
            RequestCategory.ELECTRICITY,
            "24 часа",
            (
                "ПП РФ № 354, прил. 1, п. 9: допустимый перерыв - 24 часа при одном "
                "источнике питания, 2 часа при двух"
            ),
        ),
        (RequestCategory.ELEVATOR, "24 часа", None),
        (RequestCategory.YARD, "3 суток", None),
        (RequestCategory.ENTRANCE, "3 суток", None),
        (
            RequestCategory.METER_ERROR,
            "10 рабочих дней",
            (
                "ПП РФ № 354, п. 31 «е(2)»: проверить счетчик - не позднее 10 "
                "рабочих дней со дня заявления"
            ),
        ),
        (RequestCategory.OTHER, "10 рабочих дней", "ПП РФ № 416, п. 36"),
    ],
)
def test_a_deadline_names_its_norm_or_none(
    category: RequestCategory,
    text: str,
    basis: str | None,
) -> None:
    rule = CATEGORY_RULES[category]

    assert (rule.deadline_text, rule.basis, rule.react_text) == (text, basis, None)


async def test_a_card_carries_the_stored_deadline_and_its_basis(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    leak = await service.create(own.user_id, own.house_id, _draft())
    yard = await service.create(
        own.user_id,
        own.house_id,
        _draft(category=RequestCategory.YARD),
    )

    leak_card = RequestCard.of(leak, [], [])
    yard_card = RequestCard.of(yard, [], [])

    created = leak.request.created_at
    assert (leak_card.deadline_at, leak_card.react_deadline_at) == (
        created + timedelta(days=3),
        created + timedelta(minutes=30),
    )
    assert leak_card.deadline_basis == CATEGORY_RULES[RequestCategory.LEAK].basis
    assert yard_card.deadline_at == yard.request.created_at + timedelta(hours=72)
    assert (yard_card.react_deadline_at, yard_card.deadline_basis) == (None, None)


MOSCOW = ZoneInfo("Europe/Moscow")


@pytest.mark.parametrize(
    ("created", "deadline"),
    [
        (datetime(2026, 9, 28, 9, tzinfo=UTC), date(2026, 10, 12)),
        (datetime(2026, 12, 25, 9, tzinfo=UTC), date(2027, 1, 19)),
        (datetime(2026, 12, 29, 9, tzinfo=UTC), date(2027, 1, 21)),
        (datetime(2027, 2, 15, 9, tzinfo=UTC), date(2027, 3, 2)),
        (datetime(2026, 9, 27, 20, 59, tzinfo=UTC), date(2026, 10, 9)),
        (datetime(2026, 9, 27, 21, 1, tzinfo=UTC), date(2026, 10, 12)),
        (datetime(2027, 12, 24, 9, tzinfo=UTC), date(2028, 1, 17)),
    ],
)
def test_an_answer_is_due_by_the_end_of_the_tenth_working_day(
    created: datetime,
    deadline: date,
) -> None:
    rule = CATEGORY_RULES[RequestCategory.CHARGE_DISPUTE]

    react, fix = rule.deadlines(created, MOSCOW)

    assert react is None
    local = fix.astimezone(MOSCOW)
    assert (local.date(), local.time()) == (deadline, time.max)
    assert rule.deadline_text == "10 рабочих дней"
    assert rule.basis is not None
    assert "ПП РФ № 416, п. 36" in rule.basis
    assert "п. 31 «д»" in rule.basis


async def test_request_accepts_two_videos_but_refuses_a_third_on_create_and_repeat(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    videos = [
        photo_name().replace(".jpg", suffix) for suffix in (".mp4", ".mov", ".mp4")
    ]
    card = await service.create(
        own.user_id,
        own.house_id,
        _draft(attachments=videos[:2]),
    )
    assert [photo.path for photo in card.issue_attachments] == videos[:2]
    with pytest.raises(InvalidRequest, match="не больше 2 видео"):
        await service.create(own.user_id, own.house_id, _draft(attachments=videos))
    card.request.status = RequestStatus.DONE
    await session.flush()
    with pytest.raises(InvalidRequest, match="не больше 2 видео"):
        await service.repeat(own.user_id, card.request.id, "Снова течёт", videos)


@pytest.mark.parametrize(
    "status",
    [RequestStatus.NEW, RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS],
)
async def test_the_author_cancels_an_open_request_with_a_reason(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    status: RequestStatus,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = created.request.id
    created.request.status = status
    await session.flush()

    card = await service.cancel(
        own.user_id,
        request_id,
        CancelReason.RESOLVED,
        "  Сосед перекрыл кран  ",
    )

    request = card.request
    assert request.status is RequestStatus.DONE
    assert request.completion_reason is RequestCompletionReason.RESIDENT_CANCELED
    assert request.done_at is not None
    assert request.reviewed_at is None
    last = (await _logs(session, request_id))[-1]
    assert (last.from_status, last.to_status) == (status, RequestStatus.DONE)
    assert (last.by_role, last.by_user_id) == (RequestActorRole.RESIDENT, own.user_id)
    [message] = card.messages
    assert message.message.text == (
        "↩️ Отменена: проблема решилась сама. Сосед перекрыл кран"
    )
    assert message.message.author_user_id == own.user_id
    [canceled] = await events_of(session, EventType.REQUEST_CANCELED)
    assert canceled.payload == {
        "request_id": request_id,
        "reason": "resolved",
        "status": status.value,
    }
    [changed] = await events_of(session, EventType.REQUEST_STATUS_CHANGED)
    assert changed.payload["from"] == status.value
    assert changed.payload["to"] == RequestStatus.DONE.value


@pytest.mark.parametrize("status", [RequestStatus.ON_REVIEW, RequestStatus.DONE])
async def test_a_request_past_the_work_is_not_canceled(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    status: RequestStatus,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    created.request.status = status
    await session.flush()

    with pytest.raises(InvalidState, match="на приемку"):
        await service.cancel(
            own.user_id,
            created.request.id,
            CancelReason.MISTAKE,
            None,
        )
    assert created.request.completion_reason is None


async def test_cancel_rereads_a_request_sent_to_review_meanwhile(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = created.request.id
    await _close_behind_the_session(session, request_id)

    with pytest.raises(InvalidState, match="на приемку"):
        await service.cancel(own.user_id, request_id, CancelReason.MISTAKE, None)


async def test_only_the_author_cancels_a_request(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    neighbour = await _neighbour(session, own.house_id, "77")

    with pytest.raises(EntityNotFound):
        await service.cancel(neighbour, created.request.id, CancelReason.MISTAKE, None)
    assert created.request.status is RequestStatus.NEW


async def test_a_blocked_author_does_not_cancel(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights):
        await service.cancel(
            own.user_id,
            created.request.id,
            CancelReason.MISTAKE,
            None,
        )
    assert created.request.status is RequestStatus.NEW


@pytest.mark.parametrize("comment", [None, "   "])
async def test_another_reason_needs_a_comment(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    comment: str | None,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = created.request.id

    with pytest.raises(InvalidRequest, match="почему отменяете"):
        await service.cancel(own.user_id, request_id, CancelReason.OTHER, comment)

    card = await service.cancel(
        own.user_id,
        request_id,
        CancelReason.OTHER,
        "Переехал",
    )
    assert card.messages[0].message.text == "↩️ Отменена: Переехал"


async def test_a_cancel_tells_the_staff_and_the_executor(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    admin = await _member(session, own.org_id, OrgRole.ADMIN)
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    service = requests_service(session, publisher)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = created.request.id
    created.request.executor_user_id = executor
    await session.flush()
    await publisher.flush()
    broker.messages.clear()

    await service.cancel(
        own.user_id,
        request_id,
        CancelReason.FIXED_MYSELF,
        "Вызвал частного <мастера>",
    )

    await publisher.flush()
    [staff] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert staff["user_ids"] == [admin]
    assert staff["text"] == (
        f"↩️ Житель отменил заявку №{request_id} «💧 Протечка»: "
        "починили сами или вызвали мастера\n💬 Вызвал частного &lt;мастера&gt;"
    )
    assert staff["app_path"] == f"/admin/requests/{request_id}"
    [crew] = broker.enqueued(TaskName.SEND_TO_USER)
    assert crew["user_id"] == executor
    assert crew["text"] == staff["text"]
    assert broker.enqueued(TaskName.SYNC_CHAT_CARD) == [
        {"kind": "request", "ref_id": request_id, "post": False},
    ]


@pytest.mark.parametrize(
    ("user", "canceled"),
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
async def test_the_checker_cancels_none_of_its_requests(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    user: WebAppInitData,
    canceled: bool,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())

    async def cancel() -> RequestCard:
        return await cancel_request(
            created.request.id,
            user,
            _account(own.user_id),
            service,
            FilesService(make_config().files, "test-token"),
            CancelRequestRequest(reason=CancelReason.MISTAKE),
        )

    if canceled:
        card = await cancel()
        assert card.completion_reason is RequestCompletionReason.RESIDENT_CANCELED
    else:
        with pytest.raises(NotEnoughRights):
            await cancel()
        assert created.request.status is RequestStatus.NEW


async def test_a_rejection_on_review_without_a_photo_changes_nothing(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = created.request.id
    await _mark_on_review(session, request_id)

    with pytest.raises(InvalidRequest, match=REJECTION_PHOTO_REQUIRED):
        await service.repeat(own.user_id, request_id, "Не устранили протечку", [])

    request = await RequestsRepo(session).get(request_id)
    assert request is not None
    assert request.status is RequestStatus.ON_REVIEW
    _, total = await service.list_mine(own.user_id, own.house_id, None, 20, 0)
    assert total == 1


@pytest.mark.parametrize(
    "category",
    [RequestCategory.METER_ERROR, RequestCategory.CHARGE_DISPUTE],
)
async def test_a_rejection_of_paperwork_needs_no_photo(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    category: RequestCategory,
) -> None:
    service = requests_service(session)
    created = await service.create(
        own.user_id,
        own.house_id,
        _draft(category=category),
    )
    await _mark_on_review(session, created.request.id)

    repeated = await service.repeat(
        own.user_id,
        created.request.id,
        "Перерасчет так и не сделали",
        [],
    )

    assert repeated.request.parent_request_id == created.request.id
    assert repeated.issue_attachments == []


async def test_an_answer_lifts_the_question_and_reaches_the_crew(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    staff = await _member(session, own.org_id, OrgRole.EMPLOYEE)
    executor = await _member(session, own.org_id, OrgRole.EXECUTOR)
    request = await _complain(session, own.user_id, own.house_id)
    request.executor_user_id = executor
    await session.flush()
    await admin_requests_service(session).reply(
        own.org_id,
        request.id,
        "Под вами 45 или 47 квартира?",
        staff,
        question=True,
    )

    card = await requests_service(session, publisher).write(
        own.user_id,
        request.id,
        "  47  ",
        RequestChannel.MINIAPP,
    )

    assert [
        (view.message.author_role, view.message.text) for view in card.messages
    ] == [
        (RequestActorRole.STAFF, "Под вами 45 или 47 квартира?"),
        (RequestActorRole.RESIDENT, "47"),
    ]
    assert card.request.question_asked_at is None
    assert card.request.resident_answered_at is not None
    assert card.request.status is RequestStatus.NEW
    [answer] = [
        event
        for event in await events_of(session, EventType.REQUEST_MESSAGE_SENT)
        if event.user_id == own.user_id
    ]
    assert answer.payload == {
        "request_id": request.id,
        "by_role": "resident",
        "answer": True,
        "channel": "miniapp",
    }
    await publisher.flush()
    [crew] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert crew["user_ids"] == [staff]
    assert crew["text"] == (
        f"💬 Житель ответил по заявке №{request.id} «💧 Протечка»\n\n47"
    )
    assert crew["app_path"] == f"/admin/requests/{request.id}"
    [notice] = broker.enqueued(TaskName.SEND_TO_USER)
    assert (notice["user_id"], notice["text"]) == (executor, crew["text"])


async def test_only_the_author_writes_to_a_request(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own.user_id, own.house_id)
    neighbour = await _neighbour(session, own.house_id, "2")

    with pytest.raises(EntityNotFound):
        await requests_service(session).write(
            neighbour,
            request.id,
            "Это не моя заявка",
            RequestChannel.MINIAPP,
        )


async def test_a_blocked_author_cannot_write(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own.user_id, own.house_id)
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights):
        await requests_service(session).write(
            own.user_id,
            request.id,
            "47",
            RequestChannel.MINIAPP,
        )


async def test_a_message_to_a_request_closed_meanwhile_is_refused(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own.user_id, own.house_id)
    await _close_behind_the_session(session, request.id)

    with pytest.raises(InvalidState, match="подайте новую"):
        await requests_service(session).write(
            own.user_id,
            request.id,
            "47",
            RequestChannel.MINIAPP,
        )

    assert await RequestsRepo(session).list_messages(request.id) == []


async def test_an_empty_message_is_refused(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own.user_id, own.house_id)

    with pytest.raises(InvalidRequest, match="Напишите сообщение"):
        await requests_service(session).write(
            own.user_id,
            request.id,
            "   ",
            RequestChannel.MINIAPP,
        )


async def test_closing_a_request_drops_its_question_marks(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own.user_id, own.house_id)
    await _mark_on_review(session, request.id)
    request.question_asked_at = datetime.now(UTC)
    request.resident_answered_at = datetime.now(UTC)
    await session.flush()

    card = await requests_service(session).accept(own.user_id, request.id)

    assert card.request.question_asked_at is None
    assert card.request.resident_answered_at is None


async def test_classify_names_the_danger_of_a_short_text_without_the_model(
    session: AsyncSession,
) -> None:
    user_id = await add_user(session)
    classifier = StubClassifier(RequestCategory.HEATING, 90)
    service = requests_service(session, classifier=classifier)

    response = await classify_request_text(
        _account(user_id),
        service,
        ClassifyRequestRequest(text="Пахнет газом"),
        YandexQuota(),
    )

    assert (response.category, response.danger) == (None, DangerKind.GAS)
    assert await events_of(session, EventType.LLM_SUGGESTED) == []


async def test_classify_names_the_danger_past_the_quota(session: AsyncSession) -> None:
    user_id = await add_user(session)
    service = requests_service(
        session,
        classifier=StubClassifier(RequestCategory.HEATING),
    )
    quota = YandexQuota()
    for _ in range(QUOTA_CALLS):
        quota.take(user_id)

    response = await classify_request_text(
        _account(user_id),
        service,
        ClassifyRequestRequest(text="Искрит щиток на площадке у лифта"),
        quota,
    )

    assert (response.category, response.danger) == (None, DangerKind.ELECTRIC)


async def test_classify_takes_the_alarm_from_the_model_when_the_rules_are_silent(
    session: AsyncSession,
) -> None:
    user_id = await add_user(session)
    classifier = StubClassifier(RequestCategory.ELEVATOR, 80)
    service = requests_service(session, classifier=classifier)

    response = await classify_request_text(
        _account(user_id),
        service,
        ClassifyRequestRequest(text="Лифт завис между этажами, в нем бабушка"),
        YandexQuota(),
    )

    assert (response.category, response.danger) == (
        RequestCategory.ELEVATOR,
        DangerKind.LLM,
    )


async def test_a_dangerous_request_is_marked_for_the_staff_with_its_words(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    await _member(session, own.org_id, OrgRole.ADMIN)
    service = requests_service(session, publisher)

    dangerous = await service.create(
        own.user_id,
        own.house_id,
        _draft(description="Пахнет газом в подъезде у лифта"),
    )
    calm = await service.create(own.user_id, own.house_id, _draft())

    await publisher.flush()
    assert (dangerous.request.danger, calm.request.danger) == (DangerKind.GAS, None)
    texts = [task["text"] for task in broker.enqueued(TaskName.BROADCAST_TO_USERS)]
    assert texts[0].startswith(
        f"🚨 Опасность: запах газа\n🆕 Заявка №{dangerous.request.id}",
    )
    assert texts[1].startswith(f"🆕 Заявка №{calm.request.id}")
    card = RequestCard.of(dangerous, [], [])
    assert (card.danger, card.danger_phrase) == (DangerKind.GAS, "пахнет газом")
    assert RequestCard.of(calm, [], []).danger_phrase is None


def test_the_management_company_answers_for_every_category() -> None:
    zones = {category: rule.zone for category, rule in CATEGORY_RULES.items()}

    assert zones == dict.fromkeys(RequestCategory, ResponsibilityZone.MANAGEMENT)


def test_every_pp290_ref_of_a_category_names_a_point_of_the_catalog() -> None:
    catalog = Pp290Catalog.model_validate_json(PP290)
    points = {item.ref.split(",")[0] for item in catalog.items}
    refs = {category: rule.pp290_refs for category, rule in CATEGORY_RULES.items()}

    assert {ref for rule_refs in refs.values() for ref in rule_refs} <= points
    assert refs[RequestCategory.ELEVATOR] == ("п. 22", "п. 28")
    assert refs[RequestCategory.METER_ERROR] == ()
    assert refs[RequestCategory.CHARGE_DISPUTE] == ()


async def test_pp290_is_served_whole_and_cached_for_a_day() -> None:
    response = await get_pp290(_account(UserId(1)))

    catalog = Pp290Catalog.model_validate_json(bytes(response.body))
    assert response.headers["cache-control"] == "private, max-age=86400"
    assert len(catalog.items) == 144
    assert [item.ref for item in catalog.items if item.ref.startswith("п. 22,")] == [
        f"п. 22, абз. {paragraph}" for paragraph in range(2, 6)
    ]


async def _finish(
    session: AsyncSession,
    request: Request,
    reason: RequestCompletionReason,
    done_at: datetime,
) -> None:
    request.status = RequestStatus.DONE
    request.completion_reason = reason
    request.done_at = done_at
    await session.flush()


async def test_house_problems_show_open_problems_of_the_house_without_private_ones(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    make_org_house_flat_user: Fixture,
) -> None:
    service = requests_service(session)
    members, _ = await _group_of_three(session, own)
    members[0].status = RequestStatus.IN_PROGRESS
    members[1].status = RequestStatus.ACCEPTED
    for number in ("21", "22"):
        await _complain(
            session,
            await _neighbour(session, own.house_id, number),
            own.house_id,
            RequestCategory.ELECTRICITY,
        )
    await service.create(
        own.user_id,
        own.house_id,
        _draft(category=RequestCategory.HEATING),
    )
    flatmate = await add_user(session)
    await add_resident(session, flatmate, own.house_id, own.flat_id)
    garbage = await service.create(
        flatmate,
        own.house_id,
        _draft(category=RequestCategory.GARBAGE, flat_id=own.flat_id),
    )
    await _mark_on_review(session, garbage.request.id)
    house = await HousesRepo(session).get(own.house_id)
    assert house is not None
    await RequestsRepo(session).create(
        house,
        None,
        None,
        RequestCategory.YARD,
        "Яма у подъезда",
        RequestChannel.PHONE,
        None,
        None,
        is_staff_author=True,
        place=RequestPlace.HOUSE,
    )
    neighbour = await _neighbour(session, own.house_id, "31")
    for category in (RequestCategory.METER_ERROR, RequestCategory.CHARGE_DISPUTE):
        await _complain(session, neighbour, own.house_id, category)
    elevator = await _complain(
        session,
        neighbour,
        own.house_id,
        RequestCategory.ELEVATOR,
    )
    await _mark_done(session, elevator.id)
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _complain(session, other.user_id, other.house_id, RequestCategory.ENTRANCE)
    lodger = await add_user(session)
    await add_resident(session, lodger, own.house_id, None)
    claimer = await add_user(session)
    await add_resident(session, claimer, own.house_id, own.flat_id, verified=False)
    residents_repo = ResidentsRepo(session)
    resident = await residents_repo.get_for_house(own.user_id, own.house_id)
    assert resident is not None
    await residents_repo.set_verified(resident, own.flat_id, datetime.now(UTC), None)

    board = await service.house_problems(own.user_id, own.house_id, datetime.now(UTC))
    stranger_boards = [
        await service.house_problems(stranger, own.house_id, datetime.now(UTC))
        for stranger in (lodger, claimer)
    ]

    assert [
        (problem.category, problem.flats_count, problem.status, problem.mine)
        for problem in board.open
    ] == [
        (RequestCategory.LEAK, 3, RequestStatus.NEW, False),
        (RequestCategory.ELECTRICITY, 2, RequestStatus.NEW, False),
        (RequestCategory.HEATING, 1, RequestStatus.NEW, True),
        (RequestCategory.GARBAGE, 1, RequestStatus.ON_REVIEW, True),
        (RequestCategory.YARD, 1, RequestStatus.NEW, False),
    ]
    assert board.open[0].since == members[0].created_at
    for stranger_board in stranger_boards:
        assert [problem.mine for problem in stranger_board.open] == [False] * 5


async def test_house_problems_list_the_latest_work_accepted_or_closed_in_30_days(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    make_org_house_flat_user: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("zheka.core.services.request_groups.RESOLVED_SHOWN", 2)
    now = datetime.now(UTC)
    members, _ = await _group_of_three(session, own)
    await _finish(
        session,
        members[0],
        RequestCompletionReason.RESIDENT_ACCEPTED,
        now - timedelta(days=3),
    )
    for member in members[1:]:
        await _finish(
            session,
            member,
            RequestCompletionReason.AUTO_CLOSED,
            now - timedelta(days=1),
        )
    neighbour = await _neighbour(session, own.house_id, "21")
    for category, reason, ago in [
        (RequestCategory.ELEVATOR, RequestCompletionReason.RESIDENT_ACCEPTED, 120),
        (RequestCategory.GARBAGE, RequestCompletionReason.AUTO_CLOSED, 48),
        (RequestCategory.YARD, RequestCompletionReason.RESIDENT_ACCEPTED, 31 * 24),
        (RequestCategory.ENTRANCE, RequestCompletionReason.RESIDENT_REJECTED, 1),
        (RequestCategory.METER_ERROR, RequestCompletionReason.RESIDENT_ACCEPTED, 1),
    ]:
        request = await _complain(session, neighbour, own.house_id, category)
        await _finish(session, request, reason, now - timedelta(hours=ago))
    heating = [
        await _complain(session, neighbour, own.house_id, RequestCategory.HEATING),
        await _complain(session, own.user_id, own.house_id, RequestCategory.HEATING),
    ]
    await RequestsRepo(session).attach_to_group(
        heating,
        await _add_group(session, own.house_id, RequestCategory.HEATING),
    )
    await _finish(
        session,
        heating[0],
        RequestCompletionReason.RESIDENT_ACCEPTED,
        now - timedelta(hours=1),
    )
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _finish(
        session,
        await _complain(session, other.user_id, other.house_id, RequestCategory.YARD),
        RequestCompletionReason.RESIDENT_ACCEPTED,
        now - timedelta(hours=1),
    )

    board = await requests_service(session).house_problems(
        own.user_id,
        own.house_id,
        now,
    )

    assert [
        (problem.category, problem.done_at, problem.confirmed)
        for problem in board.resolved
    ] == [
        (RequestCategory.LEAK, now - timedelta(days=1), True),
        (RequestCategory.GARBAGE, now - timedelta(days=2), False),
    ]
    assert board.resolved_total == 3
    assert [(problem.category, problem.mine) for problem in board.open] == [
        (RequestCategory.HEATING, True),
    ]


async def test_house_problems_refuse_a_blocked_resident(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights):
        await requests_service(session).house_problems(
            own.user_id,
            own.house_id,
            datetime.now(UTC),
        )


def test_house_problems_name_no_neighbour_and_no_flat() -> None:
    fields = {
        *HouseProblemsResponse.model_fields,
        *OpenProblemItem.model_fields,
        *ResolvedProblemItem.model_fields,
    }

    assert fields.isdisjoint(
        {"description", "flat_number", "flat_id", "author_name", "author_user_id"},
    )


async def test_house_problems_say_where_the_first_request_of_each_is(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    neighbour = await _neighbour(session, own.house_id, "21")
    await service.create(
        neighbour,
        own.house_id,
        _draft(category=RequestCategory.HEATING, place=RequestPlace.HOUSE),
    )
    await service.create(
        own.user_id,
        own.house_id,
        _draft(category=RequestCategory.HEATING),
    )
    await _complain(session, neighbour, own.house_id)
    elevator = await _complain(
        session,
        neighbour,
        own.house_id,
        RequestCategory.ELEVATOR,
    )
    await _finish(
        session,
        elevator,
        RequestCompletionReason.RESIDENT_ACCEPTED,
        datetime.now(UTC) - timedelta(hours=1),
    )

    board = await service.house_problems(own.user_id, own.house_id, datetime.now(UTC))

    assert {problem.category: problem.place for problem in board.open} == {
        RequestCategory.HEATING: RequestPlace.HOUSE,
        RequestCategory.LEAK: RequestPlace.FLAT,
    }
    assert [(problem.category, problem.place) for problem in board.resolved] == [
        (RequestCategory.ELEVATOR, RequestPlace.HOUSE),
    ]
