from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    OrgHouseFlatUser,
    RecordingBroker,
    add_resident,
    add_user,
    admin_requests_service,
    photo_name,
    requests_service,
)

from zheka.api.schemas.requests import RequestCard
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import (
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestPlace,
    RequestStatus,
)
from zheka.core.errors import EntityNotFound, InvalidRequest, InvalidState
from zheka.core.ids import OrgId
from zheka.core.models import Request
from zheka.core.services.requests import (
    REJECTION_COMMENT_REQUIRED,
    REJECTION_PHOTO_REQUIRED,
    REJECT_NOT_ON_REVIEW,
    RETURNED_ALREADY,
    RETURN_WINDOW,
    RequestDraft,
    RequestsService,
)
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo

COMPLAINT = "Кран снова течет"


async def _file(service: RequestsService, own: OrgHouseFlatUser) -> Request:
    card = await service.create(
        own.user_id,
        own.house_id,
        RequestDraft(
            category=RequestCategory.LEAK,
            description="Течет кран на кухне",
            place=RequestPlace.FLAT,
        ),
    )
    return card.request


async def _closed(
    session: AsyncSession,
    request: Request,
    reason: RequestCompletionReason,
    age: timedelta,
) -> None:
    request.status = RequestStatus.DONE
    request.completion_reason = reason
    request.done_at = datetime.now(UTC) - age
    await session.flush()


async def _on_review(session: AsyncSession, request: Request) -> None:
    request.status = RequestStatus.ON_REVIEW
    request.reviewed_at = datetime.now(UTC)
    await session.flush()


async def _demo(session: AsyncSession, org_id: OrgId) -> None:
    org = await OrgsRepo(session).get(org_id)
    assert org is not None
    org.is_demo = True
    await session.flush()


async def _repeats(session: AsyncSession, own: OrgHouseFlatUser) -> int:
    _, total = await RequestsRepo(session).list_for_user(
        own.user_id,
        own.house_id,
        None,
        20,
        0,
    )
    return total


async def test_an_auto_closed_request_returns_once_within_the_week(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    parent = await _file(service, own)
    await _closed(session, parent, RequestCompletionReason.AUTO_CLOSED, timedelta())
    assert parent.done_at is not None
    before = await service.get_card(own.user_id, parent.id)
    assert RequestCard.of(before, [], []).return_until == parent.done_at + (
        RETURN_WINDOW
    )
    proof = photo_name()

    await service.check_return(own.user_id, parent.id)
    repeated = await service.reject(
        own.user_id,
        parent.id,
        COMPLAINT,
        [proof],
        RequestChannel.BOT,
    )

    assert repeated.request.parent_request_id == parent.id
    assert repeated.request.description == COMPLAINT
    assert repeated.request.status is RequestStatus.NEW
    assert [photo.path for photo in repeated.issue_attachments] == [proof]
    after = await service.get_card(own.user_id, parent.id)
    assert after.request.completion_reason is RequestCompletionReason.AUTO_CLOSED
    assert after.return_until is None
    with pytest.raises(InvalidState, match=RETURNED_ALREADY):
        await service.repeat(own.user_id, parent.id, COMPLAINT, [photo_name()])
    with pytest.raises(InvalidState, match=RETURNED_ALREADY):
        await service.check_return(own.user_id, parent.id)


async def test_an_auto_closed_request_does_not_return_after_the_week(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    parent = await _file(service, own)
    await _closed(
        session,
        parent,
        RequestCompletionReason.AUTO_CLOSED,
        RETURN_WINDOW + timedelta(minutes=1),
    )

    card = await service.get_card(own.user_id, parent.id)
    assert card.return_until is None
    with pytest.raises(InvalidState, match=f"№{parent.id} можно было до"):
        await service.repeat(own.user_id, parent.id, COMPLAINT, [photo_name()])
    with pytest.raises(InvalidState, match="можно было до"):
        await service.check_return(own.user_id, parent.id)
    assert await _repeats(session, own) == 1


async def test_a_return_needs_an_explanation_and_a_photo(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    parent = await _file(service, own)
    await _closed(session, parent, RequestCompletionReason.AUTO_CLOSED, timedelta())

    with pytest.raises(InvalidRequest, match=REJECTION_COMMENT_REQUIRED):
        await service.repeat(own.user_id, parent.id, None, [photo_name()])
    with pytest.raises(InvalidRequest, match=REJECTION_PHOTO_REQUIRED):
        await service.repeat(own.user_id, parent.id, COMPLAINT, [])
    assert await _repeats(session, own) == 1


async def test_a_rated_request_is_not_returned_this_way(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    parent = await _file(service, own)
    await _closed(
        session,
        parent,
        RequestCompletionReason.RESIDENT_ACCEPTED,
        timedelta(),
    )
    await service.rate(own.user_id, parent.id, 2, "Плохо")

    card = await service.get_card(own.user_id, parent.id)
    assert card.return_until is None
    with pytest.raises(InvalidState, match=REJECT_NOT_ON_REVIEW):
        await service.reject(
            own.user_id,
            parent.id,
            COMPLAINT,
            [photo_name()],
            RequestChannel.BOT,
        )
    with pytest.raises(InvalidState, match=REJECT_NOT_ON_REVIEW):
        await service.check_return(own.user_id, parent.id)
    assert await _repeats(session, own) == 1


async def test_only_the_author_returns_an_auto_closed_request(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    parent = await _file(service, own)
    await _closed(session, parent, RequestCompletionReason.AUTO_CLOSED, timedelta())
    neighbour = await add_user(session)
    await add_resident(session, neighbour, own.house_id, None)

    with pytest.raises(EntityNotFound):
        await service.repeat(neighbour, parent.id, COMPLAINT, [photo_name()])
    with pytest.raises(EntityNotFound):
        await service.check_return(neighbour, parent.id)
    assert await _repeats(session, own) == 1


async def test_the_demo_button_closes_a_review_like_the_scheduler(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    await _demo(session, own.org_id)
    service = requests_service(session, publisher)
    request = await _file(service, own)
    await _on_review(session, request)
    before = await service.get_card(own.user_id, request.id)
    assert RequestCard.of(before, [], []).can_demo_auto_close is True
    now = datetime.now(UTC)

    card = await service.demo_auto_close(own.user_id, request.id, now)

    assert card.request.status is RequestStatus.DONE
    assert card.request.completion_reason is RequestCompletionReason.AUTO_CLOSED
    assert card.can_demo_auto_close is False
    assert card.return_until == now + RETURN_WINDOW
    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_REVIEW_CARD) == [{"request_id": request.id}]
    with pytest.raises(EntityNotFound):
        await service.demo_auto_close(own.user_id, request.id, now)


async def test_the_demo_button_is_only_in_a_demo_org(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    request = await _file(service, own)
    await _on_review(session, request)

    assert (await service.get_card(own.user_id, request.id)).can_demo_auto_close is (
        False
    )
    with pytest.raises(EntityNotFound):
        await service.demo_auto_close(own.user_id, request.id, datetime.now(UTC))


async def test_the_demo_button_is_only_for_the_author(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    service = requests_service(session)
    request = await _file(service, own)
    await _on_review(session, request)
    neighbour = await add_user(session)
    await add_resident(session, neighbour, own.house_id, None)

    with pytest.raises(EntityNotFound):
        await service.demo_auto_close(neighbour, request.id, datetime.now(UTC))


async def test_the_staff_card_has_neither_the_return_nor_the_demo_button(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    await _demo(session, own.org_id)
    service = requests_service(session)
    reviewed = await _file(service, own)
    await _on_review(session, reviewed)
    closed = await _file(service, own)
    await _closed(session, closed, RequestCompletionReason.AUTO_CLOSED, timedelta())
    staff = admin_requests_service(session)

    assert (await staff.card(own.org_id, reviewed.id)).card.can_demo_auto_close is (
        False
    )
    assert (await staff.card(own.org_id, closed.id)).card.return_until is None
