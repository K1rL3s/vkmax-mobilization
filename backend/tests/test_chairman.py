from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    add_resident,
    add_user,
    chairman_service,
    events_of,
    moderation_service,
)

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import EventType, OrgRole, ResidentRole, ResidentStatus
from zheka.core.errors import EntityNotFound, InvalidState, NotEnoughRights
from zheka.core.ids import HouseId, UserId
from zheka.core.models import Resident
from zheka.core.services.chairman import ChairmanService
from zheka.infra.database.repos.chairman import ChairmanRepo
from zheka.infra.database.repos.residents import ResidentsRepo


async def _house_with_chairman(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> tuple[OrgHouseFlatUser, UserId]:
    base = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chairman_id = await add_user(session, "Председатель")
    await add_resident(
        session,
        chairman_id,
        base.house_id,
        base.flat_id,
        is_chairman=True,
    )
    return base, chairman_id


async def _neighbour(
    session: AsyncSession,
    house_id: HouseId,
    *,
    verified: bool = True,
    status: ResidentStatus = ResidentStatus.ACTIVE,
    role: ResidentRole = ResidentRole.OWNER,
) -> UserId:
    user_id = await add_user(session, "Сосед")
    await add_resident(
        session,
        user_id,
        house_id,
        None,
        role=role,
        verified=verified,
        status=status,
        block_reason="долг" if status is ResidentStatus.BLOCKED else None,
    )
    return user_id


async def _chairman_user_id(session: AsyncSession, house_id: HouseId) -> UserId | None:
    chairman = await ResidentsRepo(session).get_chairman(house_id)
    return None if chairman is None else chairman.user_id


async def test_accept_moves_the_role_and_closes_the_link(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
) -> None:
    publisher = TaskPublisher(broker)
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    service = chairman_service(session, publisher)

    handover = await service.create_handover(chairman_id, base.house_id)
    offer = await service.accept(neighbour_id, handover.code)

    assert offer.code == handover.code
    assert await _chairman_user_id(session, base.house_id) == neighbour_id
    assert (
        await ChairmanRepo(session).get_open(base.house_id, datetime.now(UTC)) is None
    )

    events = await events_of(session, EventType.CHAIRMAN_HANDED_OVER)
    assert [event.user_id for event in events] == [neighbour_id]


async def test_accept_tells_the_issuer_and_the_org_staff(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
) -> None:
    publisher = TaskPublisher(broker)
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    service = chairman_service(session, publisher)

    handover = await service.create_handover(chairman_id, base.house_id)
    await service.accept(neighbour_id, handover.code)
    await publisher.flush()

    sent = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert len(sent) == 1
    assert set(sent[0]["user_ids"]) == {chairman_id, base.user_id}
    assert "теперь председатель" in sent[0]["text"]


async def test_decline_keeps_the_role_and_closes_the_link(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
) -> None:
    publisher = TaskPublisher(broker)
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    service = chairman_service(session, publisher)

    handover = await service.create_handover(chairman_id, base.house_id)
    await service.decline(neighbour_id, handover.code)
    await publisher.flush()

    assert await _chairman_user_id(session, base.house_id) == chairman_id
    assert (
        await ChairmanRepo(session).get_open(base.house_id, datetime.now(UTC)) is None
    )
    assert "отказался" in broker.enqueued(TaskName.BROADCAST_TO_USERS)[0]["text"]


async def test_a_new_link_revokes_the_previous_one(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    service = chairman_service(session)

    first = await service.create_handover(chairman_id, base.house_id)
    second = await service.create_handover(chairman_id, base.house_id)

    with pytest.raises(InvalidState):
        await service.accept(neighbour_id, first.code)
    assert (await service.accept(neighbour_id, second.code)) is not None


async def test_revoked_link_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    service = chairman_service(session)

    handover = await service.create_handover(chairman_id, base.house_id)
    await service.revoke_handover(chairman_id, base.house_id)

    with pytest.raises(InvalidState):
        await service.accept(neighbour_id, handover.code)
    assert await _chairman_user_id(session, base.house_id) == chairman_id


async def test_expired_link_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    service = chairman_service(session)

    handover = await service.create_handover(chairman_id, base.house_id)
    handover.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.flush()

    with pytest.raises(InvalidState):
        await service.accept(neighbour_id, handover.code)
    assert await _chairman_user_id(session, base.house_id) == chairman_id


async def test_link_is_refused_to_a_stranger_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    other = await make_org_house_flat_user()
    stranger_id = await _neighbour(session, other.house_id)
    service = chairman_service(session)

    handover = await service.create_handover(chairman_id, base.house_id)

    with pytest.raises(NotEnoughRights):
        await service.accept(stranger_id, handover.code)
    assert await _chairman_user_id(session, base.house_id) == chairman_id


@pytest.mark.parametrize(
    "taker",
    [
        {"verified": False},
        {"status": ResidentStatus.BLOCKED},
        {"role": ResidentRole.TENANT},
    ],
    ids=["unverified", "blocked", "tenant"],
)
async def test_link_is_refused_to_an_unverified_blocked_or_tenant_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    taker: dict[str, object],
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id, **taker)  # type: ignore[arg-type]
    service = chairman_service(session)

    handover = await service.create_handover(chairman_id, base.house_id)

    with pytest.raises(NotEnoughRights):
        await service.offer(neighbour_id, handover.code)
    with pytest.raises(NotEnoughRights):
        await service.accept(neighbour_id, handover.code)
    assert await _chairman_user_id(session, base.house_id) == chairman_id


async def test_link_dies_with_the_issuer_losing_the_role(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    residents = ResidentsRepo(session)
    service = chairman_service(session)

    handover = await service.create_handover(chairman_id, base.house_id)
    await residents.clear_chairman(base.house_id)

    with pytest.raises(InvalidState):
        await service.accept(neighbour_id, handover.code)


async def test_only_the_acting_chairman_issues_a_link(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, _ = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    service = chairman_service(session)

    with pytest.raises(NotEnoughRights):
        await service.create_handover(neighbour_id, base.house_id)


async def test_a_house_without_the_caller_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, _ = await _house_with_chairman(session, make_org_house_flat_user)
    outsider_id = await add_user(session, "Прохожий")
    service = chairman_service(session)

    with pytest.raises(EntityNotFound):
        await service.create_handover(outsider_id, base.house_id)


async def test_the_chairman_cannot_accept_their_own_link(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    service = chairman_service(session)

    handover = await service.create_handover(chairman_id, base.house_id)

    with pytest.raises(InvalidState):
        await service.accept(chairman_id, handover.code)


async def test_a_second_chairman_of_one_house_falls_on_the_index(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    service = chairman_service(session)

    handover = await service.create_handover(chairman_id, base.house_id)
    await service.accept(neighbour_id, handover.code)

    session.add(
        Resident(
            user_id=await add_user(session, "Самозванец"),
            house_id=base.house_id,
            flat_id=None,
            role=ResidentRole.OWNER,
            is_chairman=True,
        ),
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_open_handover_is_visible_to_the_chairman_alone(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    service: ChairmanService = chairman_service(session)

    created = await service.create_handover(chairman_id, base.house_id)
    seen = await service.open_handover(chairman_id, base.house_id)

    assert seen is not None
    assert seen.code == created.code
    with pytest.raises(NotEnoughRights):
        await service.open_handover(neighbour_id, base.house_id)


async def test_a_blocked_chairman_issues_nothing(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    chairman = await ResidentsRepo(session).get_for_house(chairman_id, base.house_id)
    assert chairman is not None
    await ResidentsRepo(session).set_status(chairman, ResidentStatus.BLOCKED, "долг")
    service = chairman_service(session)

    with pytest.raises(NotEnoughRights):
        await service.create_handover(chairman_id, base.house_id)


async def test_a_blocked_resident_can_still_decline(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
) -> None:
    publisher = TaskPublisher(broker)
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    service = chairman_service(session, publisher)
    handover = await service.create_handover(chairman_id, base.house_id)

    neighbour = await ResidentsRepo(session).get_for_house(neighbour_id, base.house_id)
    assert neighbour is not None
    await ResidentsRepo(session).set_status(neighbour, ResidentStatus.BLOCKED, "долг")

    await service.decline(neighbour_id, handover.code)
    await publisher.flush()

    assert (
        await ChairmanRepo(session).get_open(base.house_id, datetime.now(UTC)) is None
    )
    assert "отказался" in broker.enqueued(TaskName.BROADCAST_TO_USERS)[0]["text"]


async def test_an_org_reassignment_wins_over_a_link_in_flight(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    neighbour_id = await _neighbour(session, base.house_id)
    third_id = await _neighbour(session, base.house_id)
    service = chairman_service(session)
    handover = await service.create_handover(chairman_id, base.house_id)

    third = await ResidentsRepo(session).get_for_house(third_id, base.house_id)
    assert third is not None
    await moderation_service(session).set_chairman(
        base.org_id,
        third.id,
        value=True,
        by=base.user_id,
    )

    with pytest.raises(InvalidState):
        await service.accept(neighbour_id, handover.code)
    assert await _chairman_user_id(session, base.house_id) == third_id


async def test_a_new_chairman_does_not_see_the_link_of_the_previous_one(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    successor_id = await _neighbour(session, base.house_id)
    service = chairman_service(session)
    await service.create_handover(chairman_id, base.house_id)

    successor = await ResidentsRepo(session).get_for_house(successor_id, base.house_id)
    assert successor is not None
    await moderation_service(session).set_chairman(
        base.org_id,
        successor.id,
        value=True,
        by=base.user_id,
    )

    assert await service.open_handover(successor_id, base.house_id) is None


async def test_the_org_cannot_appoint_a_tenant(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _house_with_chairman(session, make_org_house_flat_user)
    tenant_id = await _neighbour(session, base.house_id, role=ResidentRole.TENANT)
    tenant = await ResidentsRepo(session).get_for_house(tenant_id, base.house_id)
    assert tenant is not None

    with pytest.raises(InvalidState, match="собственник"):
        await moderation_service(session).set_chairman(
            base.org_id,
            tenant.id,
            value=True,
            by=base.user_id,
        )
    assert await _chairman_user_id(session, base.house_id) == chairman_id
