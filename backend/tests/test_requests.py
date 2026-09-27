from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    StubClassifier,
    add_user,
    admin_requests_service,
    events_of,
    make_config,
    photo_name,
    requests_service,
)

from zheka.api.dependencies.current_account import CurrentAccount
from zheka.api.routes.requests import classify_request_text, export_request
from zheka.api.schemas.requests import (
    AdminRequestCard,
    ClassifyRequestRequest,
    CreateRequestRequest,
    RequestCard,
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
    RequestCompletionReason,
    RequestGroupStatus,
    RequestPhotoKind,
    RequestStatus,
    ResidentRole,
    ResidentStatus,
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
    MAX_PHOTOS,
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
    photos: Sequence[str] = (),
    group_id: RequestGroupId | None = None,
) -> RequestDraft:
    return RequestDraft(
        category=category,
        description=description,
        flat_id=flat_id,
        photos=photos,
        group_id=group_id,
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
        RequestDraft(category=category, description="Течет стояк"),
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
        .values(created_at=datetime.now(UTC) - timedelta(hours=hours))
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
        _draft(flat_id=own.flat_id, photos=names),
    )

    request_id = card.request.id
    assert card.request.status is RequestStatus.NEW
    assert card.request.channel is RequestChannel.MINIAPP
    assert card.request.flat_id == own.flat_id
    assert card.request.is_staff_author is False
    assert [photo.path for photo in card.issue_photos] == names
    [log] = await _logs(session, request_id)
    assert log.from_status is None
    assert log.to_status is RequestStatus.NEW
    assert log.by_role == RequestActorRole.RESIDENT
    assert log.by_user_id == own.user_id
    [event] = await events_of(session, EventType.REQUEST_CREATED)
    assert event.payload["has_photo"] is True
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
        (_draft(photos=[photo_name() for _ in range(MAX_PHOTOS + 1)]), InvalidRequest),
        (_draft(photos=["../../etc/passwd"]), EntityNotFound),
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
    assert card.normative_hours == 24
    admin_card = AdminRequestCard.of_admin(
        await admin_requests_service(session).card(other.org_id, created.request.id),
        [],
        [],
    )
    assert (admin_card.org_name, admin_card.normative_hours) == (org.name, 24)
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
        _draft(photos=[photo_name()]),
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
    assert [(row.request.id, row.has_photos) for row in rows] == [
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

    repeated = await service.repeat(
        own.user_id,
        parent_id,
        "Не устранили протечку под ванной",
        [],
        channel=RequestChannel.BOT,
    )

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
        _draft(flat_id=own.flat_id, photos=[photo_name()]),
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
    assert len(repeated.issue_photos) == 1
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
    created = await service.create(own.user_id, own.house_id, _draft(photos=[issue]))
    request_id = created.request.id
    await admin.reply(own.org_id, request_id, "Сантехник будет завтра", staff)
    for target in (
        RequestStatus.ACCEPTED,
        RequestStatus.IN_PROGRESS,
        RequestStatus.ON_REVIEW,
    ):
        await admin.change_status(own.org_id, request_id, target, None, staff)
    await RequestsRepo(session).add_photo(
        request_id,
        result,
        RequestPhotoKind.RESULT,
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
    deadline = house.local(created.request.deadline_at)
    assert first["text"] == (
        f"🆕 Заявка №{created.request.id} «💧 Протечка»\n🏢 {house.address}\n"
        f"⏰ Срок: до {deadline:%H:%M %d.%m}"
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
    monkeypatch.setattr("zheka.infra.yandex.quota.monotonic", lambda: clock[0])

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
