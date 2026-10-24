from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    add_user,
    admin_requests_service,
    events_of,
    make_notifications_service,
    requests_service,
)
from tests.test_access import _make_service as access_service
from tests.test_idempotency import Cabinet, cabinet  # noqa: F401

from zheka.api.dependencies.current_org import CurrentOrg
from zheka.api.schemas.requests import AdminRequestCard
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core import texts
from zheka.core.enums import (
    CancelReason,
    EventType,
    OrgRole,
    RequestActorRole,
    RequestCategory,
    RequestChannel,
    RequestPlace,
    RequestStatus,
    ResidentRole,
)
from zheka.core.errors import EntityNotFound, InvalidRequest, InvalidState
from zheka.core.ids import AccessSlotId, OrgId, RequestId, UserId
from zheka.core.models import Request
from zheka.core.services.admin_requests import (
    AdminRequestCardData,
    PhoneRequestDraft,
)
from zheka.core.services.events import EventsService
from zheka.core.services.requests import RequestDraft
from zheka.core.services.visits import (
    BAD_MINUTES,
    DUPLICATE_WINDOWS,
    NOT_OPEN,
    NOT_PERSONAL,
    NO_AUTHOR,
    NO_VISIT,
    PAST_WINDOW,
    REQUEST_CLOSED,
    VISIT_CANCELED,
    VISIT_NOT_FOUND,
    VISIT_REPLACED,
    VISIT_UNDER_WAY,
    WINDOWS_COUNT,
    WINDOW_NOT_FOUND,
    WINDOW_OFF_DATE,
    VisitDraft,
    VisitService,
)
from zheka.infra.database.models import OrgMember
from zheka.infra.database.repos.access import AccessRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.tables.access import access_slots_table
from zheka.infra.database.tables.requests import requests_table
from zheka.infra.database.tables.residents import residents_table

MOSCOW = ZoneInfo("Europe/Moscow")


def _service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
) -> VisitService:
    return VisitService(
        AccessRepo(session),
        RequestsRepo(session),
        HousesRepo(session),
        EventsService(EventsRepo(session)),
        make_notifications_service(session, publisher),
        requests_service(session, publisher),
    )


def _tomorrow() -> date:
    return datetime.now(MOSCOW).date() + timedelta(days=1)


def _draft(
    *hours: int,
    day: date | None = None,
    minutes: int = 120,
) -> VisitDraft:
    on = day or _tomorrow()
    return VisitDraft(
        date=on,
        starts=[datetime.combine(on, time(hour)) for hour in hours or (10, 12)],
        minutes=minutes,
    )


async def _complain(session: AsyncSession, own: OrgHouseFlatUser) -> Request:
    card = await requests_service(session).create(
        own.user_id,
        own.house_id,
        RequestDraft(
            category=RequestCategory.LEAK,
            description="Течет стояк",
            flat_id=own.flat_id,
            place=RequestPlace.FLAT,
        ),
    )
    return card.request


async def _propose(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    request: Request,
    draft: VisitDraft | None = None,
) -> None:
    await _service(session).propose(
        own.org_id,
        request.id,
        own.user_id,
        draft or _draft(),
    )


async def test_a_proposal_shows_windows_on_both_cards(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own)

    await _propose(session, own, request)

    card = await requests_service(session).get_card(own.user_id, request.id)
    assert card.visit is not None
    assert card.visit.slot_id is None
    assert [
        (window.starts_at.astimezone(MOSCOW).hour, window.minutes)
        for window in card.visit.windows
    ] == [(10, 120), (12, 120)]
    staff = await admin_requests_service(session).card(own.org_id, request.id)
    assert staff.card.visit == card.visit


async def test_a_proposal_is_written_into_the_conversation(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own)
    day = _tomorrow()

    await _propose(session, own, request, _draft(10, 12, day=day))

    card = await requests_service(session).get_card(own.user_id, request.id)
    [message] = [view.message for view in card.messages]
    assert message.author_role == RequestActorRole.STAFF.value
    assert "10:00–12:00, 12:00–14:00" in message.text
    assert f"{day.day} " in message.text
    [event] = await events_of(session, EventType.VISIT_PROPOSED)
    assert event.payload["request_id"] == request.id


async def test_a_visit_stays_out_of_access_lists(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    request = await _complain(session, own)
    await _propose(session, own, request)
    access = access_service(session)

    assert await access.list_for_org(own.org_id, None) == []
    assert await access.list_for_resident(own.flat_id, verified=True) == []


async def test_a_visit_is_not_reachable_as_an_access_request(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    stmt = (
        update(residents_table)
        .where(residents_table.c.user_id == own.user_id)
        .values(verified_at=datetime.now(MOSCOW))
    )
    await session.execute(stmt)
    request = await _complain(session, own)
    await _propose(session, own, request)
    card = await requests_service(session).get_card(own.user_id, request.id)
    assert card.visit is not None
    access = access_service(session)

    with pytest.raises(EntityNotFound):
        await access.grid(own.org_id, card.visit.id)
    with pytest.raises(EntityNotFound):
        await access.pick(own.user_id, card.visit.id, card.visit.windows[0].id)


async def test_a_house_request_takes_no_visit(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    card = await requests_service(session).create(
        own.user_id,
        own.house_id,
        RequestDraft(
            category=RequestCategory.ELEVATOR,
            description="Лифт стоит",
            flat_id=own.flat_id,
            place=RequestPlace.HOUSE,
        ),
    )

    with pytest.raises(InvalidState, match=NOT_PERSONAL):
        await _propose(session, own, card.request)


async def test_a_request_without_author_takes_no_visit(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    data = await admin_requests_service(session).create_phone(
        own.org_id,
        PhoneRequestDraft(
            house_id=own.house_id,
            category=RequestCategory.LEAK,
            description="Течет",
            flat_id=own.flat_id,
            place=RequestPlace.FLAT,
        ),
        own.user_id,
    )

    with pytest.raises(InvalidState, match=NO_AUTHOR):
        await _propose(session, own, data.card.request)


async def test_a_request_on_review_takes_no_visit(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own)
    staff = admin_requests_service(session)
    for status in (
        RequestStatus.ACCEPTED,
        RequestStatus.IN_PROGRESS,
        RequestStatus.ON_REVIEW,
    ):
        await staff.change_status(own.org_id, request.id, status, None, own.user_id)

    with pytest.raises(InvalidState, match=NOT_OPEN):
        await _propose(session, own, request)


async def test_a_new_proposal_replaces_the_current_one(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    publisher: TaskPublisher,
    broker: RecordingBroker,
) -> None:
    request = await _complain(session, own)
    service = _service(session, publisher)
    old = await service.propose(own.org_id, request.id, own.user_id, _draft())
    await service.pick(
        own.user_id,
        request.id,
        old.windows[0].id,
        RequestChannel.MINIAPP,
    )

    new = await service.propose(own.org_id, request.id, own.user_id, _draft(15))
    await publisher.flush()

    card = await requests_service(session).get_card(own.user_id, request.id)
    assert card.visit is not None
    assert card.visit.id == new.id
    assert card.visit.slot_id is None
    assert [window.id for window in card.visit.windows] == [new.windows[0].id]
    assert [sent["visit_id"] for sent in broker.enqueued(TaskName.SEND_VISIT_CARD)] == [
        old.id,
        new.id,
    ]
    with pytest.raises(InvalidState, match=VISIT_REPLACED):
        await service.pick(
            own.user_id,
            request.id,
            old.windows[1].id,
            RequestChannel.MINIAPP,
        )


async def test_a_refused_proposal_keeps_the_current_visit(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own)
    service = _service(session)
    old = await service.propose(own.org_id, request.id, own.user_id, _draft())

    with pytest.raises(InvalidRequest, match=BAD_MINUTES):
        await service.propose(own.org_id, request.id, own.user_id, _draft(minutes=5))

    card = await requests_service(session).get_card(own.user_id, request.id)
    assert card.visit is not None
    assert card.visit.id == old.id


async def test_staff_cancel_tells_the_author_and_closes_the_visit(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    publisher: TaskPublisher,
    broker: RecordingBroker,
) -> None:
    request_id = await _proposed(session, own)
    [first, _] = await _windows(session, own, request_id)
    service = _service(session, publisher)

    await service.cancel(own.org_id, request_id, own.user_id)
    await publisher.flush()

    card = await requests_service(session).get_card(own.user_id, request_id)
    assert card.visit is None
    [sent] = broker.enqueued(TaskName.SEND_TO_USER)
    assert sent["user_id"] == own.user_id
    assert sent["text"].startswith(f"❌ УК отменила визит по заявке №{request_id}")
    assert len(await events_of(session, EventType.VISIT_CANCELED)) == 1
    with pytest.raises(InvalidState, match=VISIT_CANCELED):
        await service.pick(own.user_id, request_id, first, RequestChannel.MINIAPP)


async def test_cancel_without_a_visit_is_not_found(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own)

    with pytest.raises(EntityNotFound, match=NO_VISIT):
        await _service(session).cancel(own.org_id, request.id, own.user_id)


async def test_cancel_on_a_closed_request_is_not_found(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    await requests_service(session).cancel(
        own.user_id,
        request_id,
        CancelReason.RESOLVED,
        None,
    )

    with pytest.raises(EntityNotFound, match=NO_VISIT):
        await _service(session).cancel(own.org_id, request_id, own.user_id)


async def test_cancel_of_another_org_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    other = await make_org_house_flat_user()

    with pytest.raises(EntityNotFound):
        await _service(session).cancel(other.org_id, request_id, own.user_id)


async def test_a_request_of_another_org_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    own: OrgHouseFlatUser,
) -> None:
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    alien = await _complain(session, other)

    with pytest.raises(EntityNotFound):
        await _propose(session, own, alien)


@pytest.mark.parametrize(
    ("draft", "refusal"),
    [
        (VisitDraft(date=_tomorrow(), starts=[], minutes=60), WINDOWS_COUNT),
        (_draft(8, 9, 10, 11, 12, 13, minutes=60), WINDOWS_COUNT),
        (_draft(10, minutes=10), BAD_MINUTES),
        (_draft(10, minutes=300), BAD_MINUTES),
        (_draft(10, 10), DUPLICATE_WINDOWS),
        (
            VisitDraft(
                date=_tomorrow(),
                starts=[datetime.combine(_tomorrow() + timedelta(days=1), time(10))],
                minutes=60,
            ),
            WINDOW_OFF_DATE,
        ),
        (
            _draft(0, day=datetime.now(MOSCOW).date() - timedelta(days=1)),
            PAST_WINDOW,
        ),
    ],
)
async def test_bad_windows_are_refused(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    draft: VisitDraft,
    refusal: str,
) -> None:
    request = await _complain(session, own)

    with pytest.raises(InvalidRequest, match=refusal):
        await _propose(session, own, request, draft)


async def _proposed(session: AsyncSession, own: OrgHouseFlatUser) -> RequestId:
    request = await _complain(session, own)
    await _propose(session, own, request)
    return request.id


async def _windows(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    request_id: RequestId,
) -> list[AccessSlotId]:
    card = await requests_service(session).get_card(own.user_id, request_id)
    assert card.visit is not None
    return [window.id for window in card.visit.windows]


async def test_the_author_picks_and_changes_a_window(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    first, second = await _windows(session, own, request_id)
    service = _service(session)

    picked = await service.pick(own.user_id, request_id, first, RequestChannel.MINIAPP)
    assert picked.slot_id == first
    changed = await service.pick(
        own.user_id,
        request_id,
        second,
        RequestChannel.MINIAPP,
    )
    await service.pick(own.user_id, request_id, second, RequestChannel.MINIAPP)
    assert changed.picked is not None
    assert changed.picked.id == second
    staff = await admin_requests_service(session).card(own.org_id, request_id)
    assert staff.card.visit is not None
    assert staff.card.visit.slot_id == second
    assert len(await events_of(session, EventType.VISIT_SLOT_PICKED)) == 2
    day = texts.short_day(_tomorrow())
    assert [
        view.message.text
        for view in staff.card.messages
        if view.message.author_role == RequestActorRole.RESIDENT.value
    ] == [
        texts.visit_chosen(f"{day}, 10:00–12:00", None),
        texts.visit_chosen(f"{day}, 12:00–14:00", "10:00–12:00"),
    ]
    assert staff.card.request.resident_answered_at is not None


async def _start(session: AsyncSession, slot_id: AccessSlotId) -> None:
    stmt = (
        update(access_slots_table)
        .where(access_slots_table.c.id == slot_id)
        .values(starts_at=datetime.now(UTC) - timedelta(minutes=5))
    )
    await session.execute(stmt)
    session.expire_all()


async def test_a_started_window_is_not_picked(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    first, second = await _windows(session, own, request_id)
    await _start(session, first)
    service = _service(session)

    with pytest.raises(InvalidState, match=PAST_WINDOW):
        await service.pick(own.user_id, request_id, first, RequestChannel.MINIAPP)
    picked = await service.pick(own.user_id, request_id, second, RequestChannel.BOT)

    assert picked.slot_id == second


async def test_a_started_visit_is_neither_moved_nor_declined(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    first, second = await _windows(session, own, request_id)
    service = _service(session)
    picked = await service.pick(own.user_id, request_id, first, RequestChannel.MINIAPP)
    await _start(session, first)

    with pytest.raises(InvalidState, match=VISIT_UNDER_WAY):
        await service.pick(own.user_id, request_id, second, RequestChannel.MINIAPP)
    with pytest.raises(InvalidState, match=VISIT_UNDER_WAY):
        await service.decline(own.user_id, request_id, picked.id, RequestChannel.BOT)
    again = await service.pick(own.user_id, request_id, first, RequestChannel.BOT)

    assert again.slot_id == first


async def test_only_the_author_picks(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    [first, _] = await _windows(session, own, request_id)
    stranger = await add_user(session)

    with pytest.raises(EntityNotFound):
        await _service(session).pick(
            stranger,
            request_id,
            first,
            RequestChannel.MINIAPP,
        )


async def test_a_window_of_another_request_is_not_found(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    other_id = await _proposed(session, own)
    [foreign, _] = await _windows(session, own, other_id)

    with pytest.raises(EntityNotFound, match=WINDOW_NOT_FOUND):
        await _service(session).pick(
            own.user_id,
            request_id,
            foreign,
            RequestChannel.MINIAPP,
        )


async def test_a_closed_request_has_no_visit(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    [first, _] = await _windows(session, own, request_id)
    await requests_service(session).cancel(
        own.user_id,
        request_id,
        CancelReason.RESOLVED,
        None,
    )

    card = await requests_service(session).get_card(own.user_id, request_id)
    assert card.visit is None
    with pytest.raises(InvalidState, match=REQUEST_CLOSED):
        await _service(session).pick(
            own.user_id,
            request_id,
            first,
            RequestChannel.MINIAPP,
        )


async def test_staff_card_offers_a_visit_only_when_one_can_be_proposed(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request = await _complain(session, own)
    staff = admin_requests_service(session)

    assert _offers(await staff.card(own.org_id, request.id))
    await _propose(session, own, request)
    assert _offers(await staff.card(own.org_id, request.id))
    await requests_service(session).cancel(
        own.user_id,
        request.id,
        CancelReason.RESOLVED,
        None,
    )
    assert not _offers(await staff.card(own.org_id, request.id))


def _offers(data: AdminRequestCardData) -> bool:
    viewer = CurrentOrg(
        org_id=OrgId(1),
        user_id=UserId(1),
        role=OrgRole.ADMIN,
        is_demo=False,
    )
    return AdminRequestCard.of_admin(data, [], [], viewer).can_propose_visit


async def test_staff_proposes_and_the_author_picks_through_the_api(
    cabinet: Cabinet,  # noqa: F811
) -> None:
    created = await cabinet.client.post(
        "/api/requests",
        headers=cabinet.headers,
        json={
            "category": RequestCategory.LEAK.value,
            "description": "Течет стояк в санузле",
            "flat_id": cabinet.flat_id,
            "place": RequestPlace.FLAT.value,
        },
    )
    request_id = created.json()["id"]
    day = _tomorrow()

    proposed = await cabinet.client.post(
        f"/api/admin/requests/{request_id}/visit",
        headers=cabinet.headers,
        json={
            "date": day.isoformat(),
            "starts": [f"{day.isoformat()}T10:00:00", f"{day.isoformat()}T12:00:00"],
            "minutes": 120,
        },
    )
    assert proposed.status_code == 200, proposed.text
    staff_card = proposed.json()
    assert staff_card["can_propose_visit"] is True
    [first, second] = staff_card["visit"]["windows"]
    assert first["minutes"] == 120

    picked = await cabinet.client.post(
        f"/api/requests/{request_id}/visit/{first['id']}",
        headers=cabinet.headers,
    )
    assert picked.status_code == 200, picked.text
    assert picked.json()["visit"]["slot_id"] == first["id"]
    moved = await cabinet.client.post(
        f"/api/requests/{request_id}/visit/{second['id']}",
        headers=cabinet.headers,
    )
    assert moved.status_code == 200, moved.text
    staff_view = await cabinet.client.get(
        f"/api/admin/requests/{request_id}",
        headers=cabinet.headers,
    )
    assert staff_view.json()["visit"]["slot_id"] == second["id"]
    short_day = texts.short_day(day)
    assert staff_view.json()["messages"][-1]["text"] == texts.visit_chosen(
        f"{short_day}, 12:00–14:00",
        "10:00–12:00",
    )
    visit_id = moved.json()["visit"]["id"]
    declined = await cabinet.client.post(
        f"/api/requests/{request_id}/visit/{visit_id}/decline",
        headers=cabinet.headers,
    )
    assert declined.status_code == 200, declined.text
    assert declined.json()["visit"]["slot_id"] is None
    assert declined.json()["messages"][-1]["text"] == texts.VISIT_NONE_FITS
    canceled = await cabinet.client.delete(
        f"/api/admin/requests/{request_id}/visit",
        headers=cabinet.headers,
    )
    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["visit"] is None
    access = await cabinet.client.get(
        "/api/admin/access-requests",
        headers=cabinet.headers,
    )
    assert access.json() == []


async def test_a_proposal_opens_the_window_in_the_bot(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    publisher: TaskPublisher,
    broker: RecordingBroker,
) -> None:
    request = await _complain(session, own)

    visit = await _service(session, publisher).propose(
        own.org_id,
        request.id,
        own.user_id,
        _draft(),
    )
    await publisher.flush()

    assert broker.enqueued(TaskName.SEND_VISIT_CARD) == [
        {"request_id": request.id, "visit_id": visit.id},
    ]


async def _with_executor(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    request_id: RequestId,
    role: OrgRole = OrgRole.EXECUTOR,
) -> UserId:
    executor = await add_user(session, "Слесарь")
    session.add(OrgMember(org_id=own.org_id, user_id=executor, role=role))
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == request_id)
        .values(executor_user_id=executor)
    )
    await session.execute(stmt)
    await session.flush()
    return executor


async def test_the_executor_hears_the_picked_window(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    publisher: TaskPublisher,
    broker: RecordingBroker,
) -> None:
    request_id = await _proposed(session, own)
    executor = await _with_executor(session, own, request_id)
    [first, _] = await _windows(session, own, request_id)
    service = _service(session, publisher)

    await service.pick(own.user_id, request_id, first, RequestChannel.MINIAPP)
    await service.pick(own.user_id, request_id, first, RequestChannel.MINIAPP)
    await publisher.flush()

    [sent] = [
        message
        for message in broker.enqueued(TaskName.SEND_TO_USER)
        if message["user_id"] == executor
    ]
    request = await RequestsRepo(session).get(request_id)
    assert request is not None
    day = texts.short_day(_tomorrow())
    assert sent["text"] == texts.resident_answered(
        request,
        texts.visit_chosen(f"{day}, 10:00–12:00", None),
    )


async def test_nobody_hears_a_pick_without_an_executor(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    publisher: TaskPublisher,
    broker: RecordingBroker,
) -> None:
    request_id = await _proposed(session, own)
    [first, _] = await _windows(session, own, request_id)

    await _service(session, publisher).pick(
        own.user_id,
        request_id,
        first,
        RequestChannel.MINIAPP,
    )
    await publisher.flush()

    assert broker.enqueued(TaskName.SEND_TO_USER) == []


async def test_a_removed_executor_hears_nothing(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    publisher: TaskPublisher,
    broker: RecordingBroker,
) -> None:
    request_id = await _proposed(session, own)
    await _with_executor(session, own, request_id, OrgRole.EMPLOYEE)
    [first, _] = await _windows(session, own, request_id)

    await _service(session, publisher).pick(
        own.user_id,
        request_id,
        first,
        RequestChannel.MINIAPP,
    )
    await publisher.flush()

    assert broker.enqueued(TaskName.SEND_TO_USER) == []


async def test_none_fits_clears_the_pick_and_writes_to_the_conversation(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    [first, _] = await _windows(session, own, request_id)
    service = _service(session)
    picked = await service.pick(own.user_id, request_id, first, RequestChannel.MINIAPP)

    await service.decline(own.user_id, request_id, picked.id, RequestChannel.BOT)
    await service.decline(own.user_id, request_id, picked.id, RequestChannel.BOT)

    card = await requests_service(session).get_card(own.user_id, request_id)
    assert card.visit is not None
    assert card.visit.slot_id is None
    resident = [
        view.message.text
        for view in card.messages
        if view.message.author_role == RequestActorRole.RESIDENT.value
    ]
    day = texts.short_day(_tomorrow())
    assert resident == [
        texts.visit_chosen(f"{day}, 10:00–12:00", None),
        texts.VISIT_NONE_FITS,
    ]
    assert card.request.resident_answered_at is not None
    assert len(await events_of(session, EventType.VISIT_DECLINED)) == 1


async def test_none_fits_after_a_new_pick_is_written_again(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    [first, _] = await _windows(session, own, request_id)
    service = _service(session)
    picked = await service.pick(own.user_id, request_id, first, RequestChannel.MINIAPP)
    await service.decline(own.user_id, request_id, picked.id, RequestChannel.BOT)

    await service.pick(own.user_id, request_id, first, RequestChannel.MINIAPP)
    await service.decline(own.user_id, request_id, picked.id, RequestChannel.BOT)

    assert len(await events_of(session, EventType.VISIT_DECLINED)) == 2


async def test_none_fits_for_another_request_is_not_found(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    other_id = await _proposed(session, own)
    card = await requests_service(session).get_card(own.user_id, other_id)
    assert card.visit is not None

    with pytest.raises(EntityNotFound, match=VISIT_NOT_FOUND):
        await _service(session).decline(
            own.user_id,
            request_id,
            card.visit.id,
            RequestChannel.BOT,
        )


async def test_none_fits_on_a_closed_request_is_refused(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    request_id = await _proposed(session, own)
    card = await requests_service(session).get_card(own.user_id, request_id)
    assert card.visit is not None
    await requests_service(session).cancel(
        own.user_id,
        request_id,
        CancelReason.RESOLVED,
        None,
    )

    with pytest.raises(InvalidState, match=REQUEST_CLOSED):
        await _service(session).decline(
            own.user_id,
            request_id,
            card.visit.id,
            RequestChannel.BOT,
        )
