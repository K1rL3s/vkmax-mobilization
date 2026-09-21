import secrets
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    OrgHouseFlatUser,
    RecordingBroker,
    make_config,
    make_notifications_service,
)

from zheka.api.dependencies.current_account import CurrentAccount
from zheka.api.routes.requests import classify_request_text, export_request
from zheka.api.schemas.requests import ClassifyRequestRequest, RequestCard
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.config import YandexConfig
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
from zheka.core.ids import FlatId, HouseId, MaxUserId, RequestGroupId, RequestId, UserId
from zheka.core.services.admin_requests import AdminRequestsService
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.request_groups import GroupingService
from zheka.core.services.requests import (
    AUTO_CLOSE_AFTER,
    MAX_PHOTOS,
    RequestDraft,
    RequestsService,
)
from zheka.core.texts import REQUEST_EXPORT_DISCLAIMER
from zheka.infra.database.models import (
    Event,
    Flat,
    OrgMember,
    Request,
    RequestGroup,
    RequestPhoto,
    RequestStatusLog,
    Resident,
    User,
)
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.events import events_table
from zheka.infra.database.tables.requests import (
    request_photos_table,
    request_status_log_table,
    requests_table,
)
from zheka.infra.yandex import YandexClassifier

DESCRIPTION = "Течет труба в ванной, вода на полу"

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


def _make_service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
    classifier: YandexClassifier | None = None,
) -> RequestsService:
    return RequestsService(
        RequestsRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        UsersRepo(session),
        OrgsRepo(session),
        FilesService(make_config().files, "test-token"),
        GroupingService(RequestsRepo(session), EventsService(EventsRepo(session))),
        make_notifications_service(session, publisher),
        EventsService(EventsRepo(session)),
        classifier or YandexClassifier(make_config().yandex),
    )


def _photo() -> str:
    # ровно то, что отдает upload_file: uuid4().hex плюс известный суффикс
    return f"{uuid4().hex}.jpg"


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


async def _add_user(session: AsyncSession) -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name="Сосед")
    session.add(user)
    await session.flush()
    return UserId(user.id)


async def _add_resident(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
) -> None:
    session.add(Resident(user_id=user_id, house_id=house_id, role=ResidentRole.OWNER))
    await session.flush()


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


async def _complain(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    category: RequestCategory = RequestCategory.LEAK,
) -> Request:
    card = await _make_service(session).create(
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
    return RequestGroupId(group.id)


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


async def _events(session: AsyncSession, type_: EventType) -> list[Event]:
    stmt = select(Event).where(events_table.c.type == type_)
    return list((await session.execute(stmt)).scalars().all())


def _account(user_id: UserId) -> CurrentAccount:
    return CurrentAccount(
        user_id=user_id,
        max_user_id=MaxUserId(secrets.randbits(48)),
        name="Житель",
        consent_at=datetime.now(UTC),
    )


async def test_create_writes_the_request_its_photos_the_log_and_the_event(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    names = [_photo(), _photo()]

    card = await _make_service(session).create(
        own.user_id,
        own.house_id,
        _draft(flat_id=own.flat_id, photos=names),
    )

    request_id = RequestId(card.request.id)
    assert card.request.status is RequestStatus.NEW
    assert card.request.channel is RequestChannel.MINIAPP
    assert card.request.flat_id == own.flat_id
    assert card.request.is_staff_author is False
    assert [photo.path for photo in card.issue_photos] == names
    stmt = select(RequestPhoto).where(request_photos_table.c.request_id == request_id)
    photos = (await session.execute(stmt)).scalars().all()
    assert {photo.kind for photo in photos} == {RequestPhotoKind.ISSUE}
    [log] = await _logs(session, request_id)
    assert log.from_status is None
    assert log.to_status is RequestStatus.NEW
    assert log.by_role == RequestActorRole.RESIDENT
    assert log.by_user_id == own.user_id
    [event] = await _events(session, EventType.REQUEST_CREATED)
    assert event.payload["has_photo"] is True
    assert event.payload["is_repeat"] is False
    assert event.payload["category"] == RequestCategory.LEAK.value


async def test_create_refuses_a_stranger(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    stranger = await _add_user(session)

    # чужой дом отвечает 404, а не 403
    with pytest.raises(EntityNotFound):
        await _make_service(session).create(stranger, own.house_id, _draft())


async def test_create_refuses_a_blocked_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights):
        await _make_service(session).create(own.user_id, own.house_id, _draft())


async def test_create_refuses_a_flat_that_is_not_the_authors(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    neighbour_flat = Flat(house_id=own.house_id, number="2")
    session.add(neighbour_flat)
    await session.flush()

    with pytest.raises(EntityNotFound):
        await _make_service(session).create(
            own.user_id,
            own.house_id,
            _draft(flat_id=FlatId(neighbour_flat.id)),
        )


@pytest.mark.parametrize(
    ("draft", "error"),
    [
        (_draft(photos=[_photo() for _ in range(MAX_PHOTOS + 1)]), InvalidRequest),
        # подделка дожила бы до карточки и уронила бы ее на подписи ссылки
        (_draft(photos=["../../etc/passwd"]), EntityNotFound),
        (_draft(description="   "), InvalidRequest),
    ],
)
async def test_create_refuses_a_bad_draft(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    draft: RequestDraft,
    error: type[ZhekaError],
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)

    with pytest.raises(error):
        await _make_service(session).create(own.user_id, own.house_id, draft)


async def test_create_marks_a_request_written_by_staff_of_the_same_org(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(
        resident_role=ResidentRole.OWNER,
        org_role=OrgRole.EMPLOYEE,
    )

    card = await _make_service(session).create(own.user_id, own.house_id, _draft())

    assert card.request.is_staff_author is True


async def test_create_joins_an_open_group_of_the_same_house_and_category(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    group_id = await _add_group(session, own.house_id)
    service = _make_service(session)

    first = await service.create(own.user_id, own.house_id, _draft(group_id=group_id))
    neighbour = await _add_user(session)
    await _add_resident(session, neighbour, own.house_id)
    second = await service.create(neighbour, own.house_id, _draft(group_id=group_id))

    assert first.request.group_id == group_id
    assert second.group_size == 2


async def test_create_refuses_a_group_of_another_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await make_org_house_flat_user()
    group_id = await _add_group(session, foreign.house_id)

    with pytest.raises(EntityNotFound):
        await _make_service(session).create(
            own.user_id,
            own.house_id,
            _draft(group_id=group_id),
        )


@pytest.mark.parametrize(
    ("category", "status", "error"),
    [
        (RequestCategory.ELEVATOR, RequestGroupStatus.OPEN, InvalidRequest),
        (RequestCategory.LEAK, RequestGroupStatus.CLOSED, InvalidState),
    ],
)
async def test_create_refuses_a_group_that_does_not_fit(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    category: RequestCategory,
    status: RequestGroupStatus,
    error: type[ZhekaError],
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    group_id = await _add_group(session, own.house_id, category, status)

    with pytest.raises(error):
        await _make_service(session).create(
            own.user_id,
            own.house_id,
            _draft(group_id=group_id),
        )


async def test_get_card_hides_a_request_of_another_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    neighbour = await _add_user(session)
    await _add_resident(session, neighbour, own.house_id)
    service = _make_service(session)
    card = await service.create(own.user_id, own.house_id, _draft())

    # сосед по дому - такой же чужой для заявки, как любой другой аккаунт
    with pytest.raises(EntityNotFound):
        await service.get_card(neighbour, RequestId(card.request.id))


async def test_card_takes_the_current_house_org_and_the_category_hours(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    other = await make_org_house_flat_user()
    service = _make_service(session)
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
        await service.get_card(own.user_id, RequestId(created.request.id)),
        [],
        [],
    )

    assert card.org_name == org.name
    assert card.normative_hours == 24


async def test_card_without_a_house_org_serializes_an_explicit_null(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    house = await HousesRepo(session).get(own.house_id)
    assert house is not None
    house.org_id = None
    await session.flush()

    card = RequestCard.of(
        await _make_service(session).create(own.user_id, own.house_id, _draft()),
        [],
        [],
    )

    assert card.model_dump(mode="json")["org_name"] is None


async def test_list_mine_shows_only_own_requests_of_the_current_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    other_house = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, other_house.house_id)
    neighbour = await _add_user(session)
    await _add_resident(session, neighbour, own.house_id)
    service = _make_service(session)

    mine = await service.create(own.user_id, own.house_id, _draft(photos=[_photo()]))
    await service.create(own.user_id, other_house.house_id, _draft())
    await service.create(neighbour, own.house_id, _draft())

    rows, total = await service.list_mine(own.user_id, own.house_id, None, 20, 0)

    assert total == 1
    assert [row.request.id for row in rows] == [mine.request.id]
    assert rows[0].has_photos is True


async def test_list_mine_filters_by_status(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    done = await service.create(own.user_id, own.house_id, _draft())
    await service.create(own.user_id, own.house_id, _draft())
    await _mark_done(session, RequestId(done.request.id))

    rows, total = await service.list_mine(
        own.user_id,
        own.house_id,
        RequestStatus.DONE,
        20,
        0,
    )

    assert total == 1
    assert [row.request.id for row in rows] == [done.request.id]


async def test_accept_closes_the_reviewed_request_and_opens_rating(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = RequestId(created.request.id)
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
    [reviewed] = await _events(session, EventType.REQUEST_REVIEWED)
    assert reviewed.payload == {"request_id": request_id, "accepted": True}
    [changed] = await _events(session, EventType.REQUEST_STATUS_CHANGED)
    assert changed.user_id == own.user_id
    assert changed.payload == {
        "request_id": request_id,
        "from": RequestStatus.ON_REVIEW.value,
        "to": RequestStatus.DONE.value,
        "by_role": RequestActorRole.RESIDENT.value,
    }


async def test_accept_refuses_a_request_outside_review(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())

    with pytest.raises(InvalidState, match="на приемке"):
        await service.accept(own.user_id, RequestId(created.request.id))


async def test_auto_close_ends_an_expired_review_once_and_tells_the_author(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session, publisher)
    now = datetime.now(UTC)
    ids = []
    for age in (AUTO_CLOSE_AFTER, timedelta(hours=47)):
        created = await service.create(own.user_id, own.house_id, _draft())
        request = await _mark_on_review(session, RequestId(created.request.id))
        request.reviewed_at = now - age
        ids.append(RequestId(created.request.id))
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
    [event] = await _events(session, EventType.REQUEST_AUTO_CLOSED)
    assert event.payload == {"request_id": stale}
    [changed] = await _events(session, EventType.REQUEST_STATUS_CHANGED)
    assert changed.user_id is None
    assert changed.payload["by_role"] == RequestActorRole.SYSTEM.value
    await publisher.flush()
    [sent] = broker.enqueued(TaskName.SEND_TO_USER)
    assert sent["user_id"] == own.user_id
    assert sent["mandatory"] is True
    assert f"№{stale}" in sent["text"]


async def test_rate_puts_the_score_and_closes_the_rating(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = RequestId(created.request.id)
    await _mark_done(session, request_id)

    rated = await service.rate(own.user_id, request_id, 4, "  Спасибо  ")

    assert rated.request.rating == 4
    assert rated.request.feedback == "Спасибо"
    assert rated.can_rate is False
    events = await _events(session, EventType.REQUEST_RATED)
    assert events[0].payload["score"] == 4
    assert events[0].payload["has_comment"] is True


async def test_rate_refuses_a_request_that_is_not_done(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    card = await service.create(own.user_id, own.house_id, _draft())

    with pytest.raises(InvalidState):
        await service.rate(own.user_id, RequestId(card.request.id), 5, None)


async def test_rate_refuses_the_second_score(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = RequestId(created.request.id)
    await _mark_done(session, request_id)
    await service.rate(own.user_id, request_id, 5, None)

    with pytest.raises(InvalidState):
        await service.rate(own.user_id, request_id, 1, None)


@pytest.mark.parametrize("rating", [0, 6])
async def test_rate_refuses_a_score_outside_the_scale(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    rating: int,
) -> None:
    # кнопка бота присылает любую строку, схему API бот не проходит вовсе
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = RequestId(created.request.id)
    await _mark_done(session, request_id)

    with pytest.raises(InvalidRequest):
        await service.rate(own.user_id, request_id, rating, None)


async def test_repeat_refuses_a_parent_that_is_not_done(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())

    with pytest.raises(InvalidState):
        await service.repeat(own.user_id, RequestId(created.request.id), None, [])


async def test_repeat_from_review_rejects_the_result_and_opens_a_new_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    parent_id = RequestId(created.request.id)
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
    reviewed = await _events(session, EventType.REQUEST_REVIEWED)
    assert reviewed[0].payload == {"request_id": parent_id, "accepted": False}
    created_events = await _events(session, EventType.REQUEST_CREATED)
    assert created_events[-1].payload["channel"] == RequestChannel.BOT.value


async def test_repeat_from_review_requires_a_comment(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    request_id = RequestId(created.request.id)
    await _mark_on_review(session, request_id)

    with pytest.raises(InvalidRequest, match="что сделано плохо"):
        await service.repeat(own.user_id, request_id, None, [])

    request = await RequestsRepo(session).get(request_id)
    assert request is not None
    assert request.status is RequestStatus.ON_REVIEW


async def test_repeat_copies_the_parent_and_starts_from_scratch(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(
        own.user_id,
        own.house_id,
        _draft(flat_id=own.flat_id, photos=[_photo()]),
    )
    parent_id = RequestId(created.request.id)
    await _mark_done(session, parent_id)

    repeated = await service.repeat(
        own.user_id,
        parent_id,
        "Течет снова, хуже прежнего",
        [_photo()],
    )

    assert repeated.request.parent_request_id == parent_id
    assert repeated.request.status is RequestStatus.NEW
    assert repeated.request.category is RequestCategory.LEAK
    assert repeated.request.flat_id == own.flat_id
    assert repeated.request.description == "Течет снова, хуже прежнего"
    assert len(repeated.issue_photos) == 1
    events = await _events(session, EventType.REQUEST_CREATED)
    assert [event.payload["is_repeat"] for event in events] == [False, True]


async def test_repeat_without_a_new_description_keeps_the_parents_one(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    parent_id = RequestId(created.request.id)
    await _mark_done(session, parent_id)

    repeated = await service.repeat(own.user_id, parent_id, None, [])

    assert repeated.request.description == DESCRIPTION


async def test_repeat_refuses_a_blocked_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())
    parent_id = RequestId(created.request.id)
    await _mark_done(session, parent_id)
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights):
        await service.repeat(own.user_id, parent_id, "Опять течет", [])


async def test_export_prints_the_whole_life_of_the_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    staff = await _add_user(session)
    session.add(OrgMember(org_id=own.org_id, user_id=staff, role=OrgRole.EMPLOYEE))
    await session.flush()
    service = _make_service(session)
    admin = AdminRequestsService(
        RequestsRepo(session),
        HousesRepo(session),
        UsersRepo(session),
        OrgsRepo(session),
        GroupingService(RequestsRepo(session), EventsService(EventsRepo(session))),
        make_notifications_service(session),
        EventsService(EventsRepo(session)),
    )
    issue = _photo()
    result = _photo()
    created = await service.create(own.user_id, own.house_id, _draft(photos=[issue]))
    request_id = RequestId(created.request.id)
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
    # фото результата в "было" выдало бы работу УК за ущерб
    assert [photo.name for photo in card.photos] == [issue]
    assert [photo.name for photo in card.result_photos] == [result]
    assert all("sig=" in photo.url for photo in [*card.photos, *card.result_photos])
    events = await _events(session, EventType.REQUEST_EXPORTED)
    assert [(event.user_id, event.payload["request_id"]) for event in events] == [
        (own.user_id, request_id),
    ]


async def test_export_hides_a_request_of_another_resident_and_records_nothing(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    neighbour = await _add_user(session)
    await _add_resident(session, neighbour, own.house_id)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())

    with pytest.raises(EntityNotFound):
        await service.export(neighbour, RequestId(created.request.id))

    assert await _events(session, EventType.REQUEST_EXPORTED) == []


class _StubClassifier(YandexClassifier):
    __slots__ = ("_category",)

    def __init__(self, category: RequestCategory | None) -> None:
        super().__init__(YandexConfig(api_key=None, folder_id=None))
        self._category = category

    async def classify(self, text: str) -> RequestCategory | None:  # noqa: ARG002
        return self._category


@pytest.mark.parametrize("category", [RequestCategory.HEATING, None])
async def test_classify_answers_the_category_with_its_zone_and_records_it(
    session: AsyncSession,
    category: RequestCategory | None,
) -> None:
    user_id = await _add_user(session)
    service = _make_service(session, classifier=_StubClassifier(category))

    response = await classify_request_text(
        _account(user_id),
        service,
        ClassifyRequestRequest(text="Батареи холодные"),
    )

    assert response.category is category
    events = await _events(session, EventType.LLM_SUGGESTED)
    if category is None:
        assert response.zone is None
        assert events == []
    else:
        assert response.zone is CATEGORY_RULES[category].zone
        assert [(event.user_id, event.payload) for event in events] == [
            (user_id, {"category": category.value}),
        ]


def test_classify_text_is_capped() -> None:
    with pytest.raises(ValidationError):
        ClassifyRequestRequest(text="а" * 4001)


@pytest.mark.parametrize(
    ("suggested", "accepted", "recorded"),
    [(True, True, True), (True, False, False), (False, True, False)],
)
async def test_create_records_an_accepted_suggestion_only_when_accepted(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    suggested: bool,
    accepted: bool,
    recorded: bool,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)

    await _make_service(session).create(
        own.user_id,
        own.house_id,
        RequestDraft(
            category=RequestCategory.ELEVATOR,
            description=DESCRIPTION,
            llm_suggested=suggested,
            llm_accepted=accepted,
        ),
    )

    events = await _events(session, EventType.LLM_ACCEPTED)
    expected = [(own.user_id, own.house_id, RequestCategory.ELEVATOR.value)]
    assert [
        (event.user_id, event.payload["house_id"], event.payload["category"])
        for event in events
    ] == (expected if recorded else [])
