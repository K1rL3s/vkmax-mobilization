import secrets
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser, make_config

from zheka.core.enums import (
    EventType,
    OrgRole,
    RequestActorRole,
    RequestCategory,
    RequestChannel,
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
)
from zheka.core.ids import FlatId, HouseId, MaxUserId, RequestGroupId, RequestId, UserId
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.requests import (
    MAX_PHOTOS,
    RequestDraft,
    RequestsService,
)
from zheka.infra.database.models import (
    Event,
    Flat,
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

DESCRIPTION = "Течет труба в ванной, вода на полу"

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


def _make_service(session: AsyncSession) -> RequestsService:
    return RequestsService(
        RequestsRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        UsersRepo(session),
        OrgsRepo(session),
        FilesService(make_config().files, "test-token"),
        EventsService(EventsRepo(session)),
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
    flat_id: FlatId | None = None,
) -> Resident:
    resident = Resident(
        user_id=user_id,
        house_id=house_id,
        flat_id=flat_id,
        role=ResidentRole.OWNER,
    )
    session.add(resident)
    await session.flush()
    return resident


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


async def _mark_done(session: AsyncSession, request_id: RequestId) -> Request:
    request = await RequestsRepo(session).get(request_id)
    assert request is not None
    request.status = RequestStatus.DONE
    request.done_at = datetime.now(UTC)
    await session.flush()
    return request


async def _logs(session: AsyncSession, request_id: RequestId) -> list[RequestStatusLog]:
    stmt = select(RequestStatusLog).where(
        request_status_log_table.c.request_id == request_id,
    )
    return list((await session.execute(stmt)).scalars().all())


async def _photos(session: AsyncSession, request_id: RequestId) -> list[RequestPhoto]:
    stmt = select(RequestPhoto).where(
        request_photos_table.c.request_id == request_id,
    )
    return list((await session.execute(stmt)).scalars().all())


async def _events(session: AsyncSession, type_: EventType) -> list[Event]:
    stmt = select(Event).where(events_table.c.type == type_)
    return list((await session.execute(stmt)).scalars().all())


async def test_create_writes_the_request_its_photos_and_the_first_log_row(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    names = [_photo(), _photo()]

    card = await service.create(
        own.user_id,
        own.house_id,
        _draft(flat_id=own.flat_id, photos=names),
    )

    assert card.request.status is RequestStatus.NEW
    assert card.request.channel is RequestChannel.MINIAPP
    assert card.request.flat_id == own.flat_id
    assert [photo.path for photo in card.issue_photos] == names
    assert all(
        photo.kind is RequestPhotoKind.ISSUE
        for photo in await _photos(session, RequestId(card.request.id))
    )
    logs = await _logs(session, RequestId(card.request.id))
    assert len(logs) == 1
    assert logs[0].from_status is None
    assert logs[0].to_status is RequestStatus.NEW
    assert logs[0].by_role == RequestActorRole.RESIDENT
    assert logs[0].by_user_id == own.user_id


async def test_create_records_the_event_with_the_photo_flag(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)

    await service.create(own.user_id, own.house_id, _draft(photos=[_photo()]))

    events = await _events(session, EventType.REQUEST_CREATED)
    assert len(events) == 1
    assert events[0].payload["has_photo"] is True
    assert events[0].payload["is_repeat"] is False
    assert events[0].payload["category"] == RequestCategory.LEAK.value


async def test_create_refuses_a_stranger(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    stranger = await _add_user(session)
    service = _make_service(session)

    # чужой дом отвечает 404, а не 403
    with pytest.raises(EntityNotFound):
        await service.create(stranger, own.house_id, _draft())


async def test_create_refuses_a_blocked_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _block(session, own.user_id, own.house_id)
    service = _make_service(session)

    with pytest.raises(NotEnoughRights):
        await service.create(own.user_id, own.house_id, _draft())


async def test_create_refuses_a_flat_that_is_not_the_authors(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    neighbour_flat = Flat(house_id=own.house_id, number="2")
    session.add(neighbour_flat)
    await session.flush()
    service = _make_service(session)

    with pytest.raises(EntityNotFound):
        await service.create(
            own.user_id,
            own.house_id,
            _draft(flat_id=FlatId(neighbour_flat.id)),
        )


async def test_create_refuses_more_photos_than_the_platform_takes(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)

    with pytest.raises(InvalidRequest):
        await service.create(
            own.user_id,
            own.house_id,
            _draft(photos=[_photo() for _ in range(MAX_PHOTOS + 1)]),
        )


async def test_create_refuses_a_photo_name_that_upload_never_produced(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)

    # подделка дожила бы до карточки и уронила бы ее на подписи ссылки
    with pytest.raises(EntityNotFound):
        await service.create(
            own.user_id,
            own.house_id,
            _draft(photos=["../../etc/passwd"]),
        )


async def test_create_refuses_an_empty_description(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)

    with pytest.raises(InvalidRequest):
        await service.create(own.user_id, own.house_id, _draft(description="   "))


async def test_create_marks_a_request_written_by_staff_of_the_same_org(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(
        resident_role=ResidentRole.OWNER,
        org_role=OrgRole.EMPLOYEE,
    )
    service = _make_service(session)

    card = await service.create(own.user_id, own.house_id, _draft())

    assert card.request.is_staff_author is True


async def test_create_does_not_mark_an_ordinary_resident_as_staff(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)

    card = await service.create(own.user_id, own.house_id, _draft())

    assert card.request.is_staff_author is False


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
    service = _make_service(session)

    with pytest.raises(EntityNotFound):
        await service.create(own.user_id, own.house_id, _draft(group_id=group_id))


async def test_create_refuses_a_group_of_another_category(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    group_id = await _add_group(session, own.house_id, RequestCategory.ELEVATOR)
    service = _make_service(session)

    with pytest.raises(InvalidRequest):
        await service.create(own.user_id, own.house_id, _draft(group_id=group_id))


async def test_create_refuses_a_closed_group(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    group_id = await _add_group(
        session,
        own.house_id,
        status=RequestGroupStatus.CLOSED,
    )
    service = _make_service(session)

    with pytest.raises(InvalidState):
        await service.create(own.user_id, own.house_id, _draft(group_id=group_id))


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


async def test_rate_refuses_a_request_that_is_not_done(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    card = await service.create(own.user_id, own.house_id, _draft())

    with pytest.raises(InvalidState):
        await service.rate(own.user_id, RequestId(card.request.id), 5, None)


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


async def test_repeat_refuses_a_parent_that_is_not_done(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    created = await service.create(own.user_id, own.house_id, _draft())

    with pytest.raises(InvalidState):
        await service.repeat(own.user_id, RequestId(created.request.id), None, [])


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


async def test_every_request_row_carries_its_status_log(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    service = _make_service(session)
    await service.create(own.user_id, own.house_id, _draft())

    requests = (await session.execute(select(requests_table.c.id))).scalars().all()
    logged = (
        (await session.execute(select(request_status_log_table.c.request_id)))
        .scalars()
        .all()
    )

    # ни один путь не меняет requests.status, не оставив строки в журнале
    assert set(requests) == set(logged)
