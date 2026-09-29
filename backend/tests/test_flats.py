from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    add_user,
    events_of,
    make_notifications_service,
)

from zheka.api.dependencies.current_residency import CurrentResidency
from zheka.api.routes.flats import verify_flat
from zheka.api.schemas.flats import (
    ACCOUNT_NO_MAX_LENGTH,
    FlatCard,
    FlatVerificationRequest,
    VerifyFlatByQrRequest,
    VerifyFlatRequest,
)
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import (
    EventType,
    OrgRole,
    ResidentRole,
    ResidentStatus,
    VerificationStatus,
)
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
    TooManyRequests,
)
from zheka.core.ids import FlatId, HouseId, UserId
from zheka.core.payment_qr import NOT_PAYMENT_QR
from zheka.core.services.events import EventsService
from zheka.core.services.flats import (
    ALREADY_VERIFIED_DETAIL,
    INVITE_ISSUER_GONE,
    MAX_INVITE_HOURS,
    MISMATCH_DETAIL,
    NOT_A_TENANT,
    REVOKED_BY_ORG,
    TENANT_BLOCKED,
    FlatsService,
)
from zheka.core.services.houses import NOT_CONNECTED
from zheka.infra.database.models import Flat, Resident, VerificationRequest
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.invites import InvitesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.quota import VERIFY_CALLS, VerifyQuota

ACCOUNT = "ЛС-0042 7781"


def _make_service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
) -> FlatsService:
    return FlatsService(
        FlatsRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        InvitesRepo(session),
        UsersRepo(session),
        OrgsRepo(session),
        make_notifications_service(session, publisher),
        EventsService(EventsRepo(session)),
    )


async def _add_flat(
    session: AsyncSession,
    house_id: HouseId,
    number: str,
    account_no: str | None = None,
) -> FlatId:
    flat = Flat(house_id=house_id, number=number, account_no=account_no)
    session.add(flat)
    await session.flush()
    return flat.id


async def _add_resident(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    flat_id: FlatId | None,
    role: ResidentRole = ResidentRole.OWNER,
    *,
    verified: bool = False,
) -> Resident:
    is_owner = role is ResidentRole.OWNER
    resident = Resident(
        user_id=user_id,
        house_id=house_id,
        flat_id=flat_id,
        role=role,
        can_see_charges=is_owner,
        can_vote=is_owner,
        verified_at=datetime.now(UTC) if verified else None,
    )
    session.add(resident)
    await session.flush()
    return resident


async def _set_account(session: AsyncSession, flat_id: FlatId, account_no: str) -> None:
    flat = await HousesRepo(session).get_flat(flat_id)
    assert flat is not None
    flat.account_no = account_no
    await session.flush()


async def _add_request(
    session: AsyncSession,
    flat_id: FlatId,
    user_id: UserId,
) -> VerificationRequest:
    request = await FlatsRepo(session).add_verification_request(
        flat_id,
        user_id,
        ACCOUNT,
        None,
    )
    assert request is not None
    return request


async def _pending_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> tuple[OrgHouseFlatUser, Resident, VerificationRequest]:
    staff = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    resident = await _add_resident(
        session,
        await add_user(session),
        staff.house_id,
        None,
    )
    request = await _add_request(session, staff.flat_id, resident.user_id)
    return staff, resident, request


async def _verified_owner(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> OrgHouseFlatUser:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)
    return own


async def test_verify_matches_the_account_ignoring_spaces_and_case(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, ACCOUNT)
    resident = await _add_resident(session, own.user_id, own.house_id, None)

    result = await _make_service(session).verify(
        own.user_id,
        own.flat_id,
        " лс-0042  7781 ",
    )

    assert result.verified is True
    assert resident.flat_id == own.flat_id
    assert resident.verified_at is not None
    assert resident.verified_by is None


@pytest.mark.parametrize(("stored", "stated"), [(ACCOUNT, "0000"), (None, "")])
async def test_verify_without_a_match_changes_nothing(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    stored: str | None,
    stated: str,
) -> None:
    own = await make_org_house_flat_user()
    if stored is not None:
        await _set_account(session, own.flat_id, stored)
    resident = await _add_resident(session, own.user_id, own.house_id, None)

    result = await _make_service(session).verify(own.user_id, own.flat_id, stated)

    assert result.verified is False
    assert resident.flat_id is None
    assert resident.verified_at is None


async def test_verify_is_idempotent_on_the_same_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    await _set_account(session, own.flat_id, ACCOUNT)

    result = await _make_service(session).verify(own.user_id, own.flat_id, ACCOUNT)

    assert result.verified is True
    assert result.detail == ALREADY_VERIFIED_DETAIL


async def test_verify_refuses_a_move_to_another_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    other_flat = await _add_flat(session, own.house_id, "2", ACCOUNT)

    with pytest.raises(InvalidState):
        await _make_service(session).verify(own.user_id, other_flat, ACCOUNT)


async def test_verify_moves_an_unverified_residency_to_the_confirmed_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    other_flat = await _add_flat(session, own.house_id, "2", ACCOUNT)
    resident = await _add_resident(session, own.user_id, own.house_id, own.flat_id)

    result = await _make_service(session).verify(own.user_id, other_flat, ACCOUNT)

    assert result.verified is True
    assert resident.flat_id == other_flat
    assert resident.verified_at is not None


async def test_verify_refuses_a_tenant(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, ACCOUNT)
    await _add_resident(
        session,
        own.user_id,
        own.house_id,
        own.flat_id,
        ResidentRole.TENANT,
    )

    with pytest.raises(NotEnoughRights):
        await _make_service(session).verify(own.user_id, own.flat_id, ACCOUNT)


async def test_verify_answers_not_found_for_a_flat_of_another_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    other = await make_org_house_flat_user()

    with pytest.raises(EntityNotFound):
        await _make_service(session).verify(own.user_id, other.flat_id, ACCOUNT)


async def test_second_pending_request_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, None)
    service = _make_service(session)
    await service.request_verification(
        own.user_id,
        own.flat_id,
        ACCOUNT,
        "я собственник",
    )

    with pytest.raises(InvalidState):
        await service.request_verification(own.user_id, own.flat_id, ACCOUNT, None)


async def test_request_verification_is_refused_for_a_verified_residency(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)

    with pytest.raises(InvalidState):
        await _make_service(session).request_verification(
            own.user_id,
            own.flat_id,
            ACCOUNT,
            None,
        )


async def test_approve_verifies_the_resident_and_notifies_them(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    staff, resident, request = await _pending_request(session, make_org_house_flat_user)

    view = await _make_service(session, publisher).approve_verification(
        staff.org_id,
        request.id,
        staff.user_id,
    )

    assert view.request.status is VerificationStatus.APPROVED
    assert view.request.decided_by == staff.user_id
    assert view.request.decided_at is not None
    assert resident.flat_id == staff.flat_id
    assert resident.verified_by == staff.user_id
    await publisher.flush()
    enqueued = broker.enqueued(TaskName.SEND_TO_USER)
    assert len(enqueued) == 1
    assert enqueued[0]["user_id"] == resident.user_id
    assert enqueued[0]["mandatory"] is True
    assert "подтвердила" in enqueued[0]["text"]


async def test_deciding_a_decided_request_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    staff, _, request = await _pending_request(session, make_org_house_flat_user)
    service = _make_service(session)
    await service.approve_verification(staff.org_id, request.id, staff.user_id)

    with pytest.raises(InvalidState):
        await service.reject_verification(
            staff.org_id,
            request.id,
            staff.user_id,
            "передумали",
        )


@pytest.mark.parametrize("reason", ["", "   "])
async def test_reject_requires_a_reason(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    reason: str,
) -> None:
    staff, _, request = await _pending_request(session, make_org_house_flat_user)

    with pytest.raises(InvalidRequest):
        await _make_service(session).reject_verification(
            staff.org_id,
            request.id,
            staff.user_id,
            reason,
        )

    assert request.status is VerificationStatus.PENDING


async def test_reject_stores_the_reason_and_sends_it_to_the_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    staff, resident, request = await _pending_request(session, make_org_house_flat_user)

    view = await _make_service(session, publisher).reject_verification(
        staff.org_id,
        request.id,
        staff.user_id,
        "  счет не ваш  ",
    )

    assert view.request.status is VerificationStatus.REJECTED
    assert view.request.reason == "счет не ваш"
    assert resident.verified_at is None
    await publisher.flush()
    enqueued = broker.enqueued(TaskName.SEND_TO_USER)
    assert len(enqueued) == 1
    assert enqueued[0]["user_id"] == resident.user_id
    assert enqueued[0]["mandatory"] is True
    assert "счет не ваш" in enqueued[0]["text"]


async def test_foreign_verification_request_is_not_found_for_another_org(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    request = await _add_request(session, other.flat_id, other.user_id)

    with pytest.raises(EntityNotFound):
        await _make_service(session).approve_verification(
            own.org_id,
            request.id,
            own.user_id,
        )


async def test_verification_requests_list_hides_another_org(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _add_request(session, other.flat_id, other.user_id)

    views, total = await _make_service(session).verification_requests(
        own.org_id,
        None,
        None,
        50,
        0,
    )

    assert total == 0
    assert views == []


@pytest.mark.parametrize(
    ("role", "verified"),
    [(ResidentRole.TENANT, True), (ResidentRole.OWNER, False)],
)
async def test_create_invite_needs_a_verified_owner(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    role: ResidentRole,
    verified: bool,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(
        session,
        own.user_id,
        own.house_id,
        own.flat_id,
        role,
        verified=verified,
    )

    with pytest.raises(NotEnoughRights):
        await _make_service(session).create_invite(own.user_id, own.flat_id, 72, 1)


@pytest.mark.parametrize(
    ("expires_in_hours", "max_activations"),
    [(0, 1), (-1, 1), (MAX_INVITE_HOURS + 1, 1), (72, 0), (72, -1)],
)
async def test_create_invite_rejects_dead_limits(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    expires_in_hours: int,
    max_activations: int,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)

    with pytest.raises(InvalidRequest):
        await _make_service(session).create_invite(
            own.user_id,
            own.flat_id,
            expires_in_hours,
            max_activations,
        )


async def test_activated_invite_makes_a_tenant_without_charges_and_votes(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    tenant_id = await add_user(session)

    view = await service.activate_invite(tenant_id, invite.code)

    assert view.resident.role is ResidentRole.TENANT
    assert view.resident.can_see_charges is False
    assert view.resident.can_vote is False
    assert view.resident.flat_id == own.flat_id
    assert view.resident.verified_at is not None
    assert view.resident.verified_by == own.user_id


async def test_single_use_flat_invite_is_not_activated_twice(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    first = await add_user(session)
    second = await add_user(session)
    await service.activate_invite(first, invite.code)

    with pytest.raises(InvalidState):
        await service.activate_invite(second, invite.code)

    used = await InvitesRepo(session).get_flat(invite.code)
    assert used is not None
    assert used.activations_used == 1
    assert await ResidentsRepo(session).get_for_house(second, own.house_id) is None


async def test_activation_by_a_resident_of_the_same_flat_consumes_nothing(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)

    view = await service.activate_invite(own.user_id, invite.code)

    assert view.resident.role is ResidentRole.OWNER
    used = await InvitesRepo(session).get_flat(invite.code)
    assert used is not None
    assert used.activations_used == 0


async def test_activation_refuses_a_resident_of_another_flat_in_the_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    neighbour_flat = await _add_flat(session, own.house_id, "2")
    neighbour = await add_user(session)
    await _add_resident(session, neighbour, own.house_id, neighbour_flat, verified=True)

    with pytest.raises(InvalidState):
        await service.activate_invite(neighbour, invite.code)

    used = await InvitesRepo(session).get_flat(invite.code)
    assert used is not None
    assert used.activations_used == 0


async def test_revoked_invite_is_dead_for_a_newcomer_and_for_the_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    await service.revoke_invite(own.user_id, invite.code)

    with pytest.raises(InvalidState):
        await service.activate_invite(await add_user(session), invite.code)
    with pytest.raises(InvalidState):
        await service.activate_invite(own.user_id, invite.code)


async def test_invite_is_not_revoked_by_a_stranger(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    neighbour_flat = await _add_flat(session, own.house_id, "2")
    neighbour = await add_user(session)
    await _add_resident(session, neighbour, own.house_id, neighbour_flat, verified=True)

    with pytest.raises(EntityNotFound):
        await service.revoke_invite(neighbour, invite.code)

    alive = await InvitesRepo(session).get_flat(invite.code)
    assert alive is not None
    assert alive.revoked_at is None


async def test_flat_card_shows_the_account_tail_only_to_a_verified_owner(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    await _set_account(session, own.flat_id, ACCOUNT)
    tenant = await add_user(session)
    await _add_resident(
        session,
        tenant,
        own.house_id,
        own.flat_id,
        ResidentRole.TENANT,
        verified=True,
    )
    unverified = await add_user(session)
    await _add_resident(session, unverified, own.house_id, own.flat_id)
    service = _make_service(session)

    owner_card = FlatCard.of(await service.flat_card(own.user_id, own.flat_id))
    tenant_card = FlatCard.of(await service.flat_card(tenant, own.flat_id))
    unverified_card = FlatCard.of(await service.flat_card(unverified, own.flat_id))

    assert owner_card.account_no == ACCOUNT[-4:]
    assert owner_card.residents_count == 3
    assert tenant_card.account_no is None
    assert unverified_card.verified is False
    assert unverified_card.account_no is None


async def test_flat_card_carries_the_latest_verification_status(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    service = _make_service(session)
    await service.request_verification(own.user_id, own.flat_id, ACCOUNT, "  ")

    card = FlatCard.of(await service.flat_card(own.user_id, own.flat_id))

    assert card.verification_status is VerificationStatus.PENDING


async def test_flat_card_is_refused_to_a_resident_of_another_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    neighbour_flat = await _add_flat(session, own.house_id, "2")
    neighbour = await add_user(session)
    await _add_resident(session, neighbour, own.house_id, neighbour_flat, verified=True)

    with pytest.raises(NotEnoughRights):
        await _make_service(session).flat_card(neighbour, own.flat_id)


async def test_request_verification_is_refused_while_the_org_is_not_connected(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(registered=False)
    await _add_resident(session, own.user_id, own.house_id, None)

    with pytest.raises(InvalidState, match=NOT_CONNECTED):
        await _make_service(session).request_verification(
            own.user_id,
            own.flat_id,
            ACCOUNT,
            None,
        )

    assert await FlatsRepo(session).get_latest_request(own.user_id, own.flat_id) is None


@pytest.mark.parametrize(
    ("role", "verified"),
    [(ResidentRole.TENANT, True), (ResidentRole.OWNER, False)],
)
async def test_invites_are_listed_only_to_a_verified_owner(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    role: ResidentRole,
    verified: bool,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    service = _make_service(session)
    await service.create_invite(own.user_id, own.flat_id, 72, 1)
    other = await add_user(session)
    await _add_resident(
        session,
        other,
        own.house_id,
        own.flat_id,
        role,
        verified=verified,
    )

    with pytest.raises(NotEnoughRights):
        await service.list_invites(other, own.flat_id)
    assert len(await service.list_invites(own.user_id, own.flat_id)) == 1


async def test_flat_residents_are_listed_only_to_a_verified_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    service = _make_service(session)
    claimant = await add_user(session)
    await _add_resident(session, claimant, own.house_id, own.flat_id)

    with pytest.raises(NotEnoughRights):
        await service.list_residents(claimant, own.flat_id)
    assert len(await service.list_residents(own.user_id, own.flat_id)) == 2


@pytest.mark.parametrize("loss", ["revoked", "blocked", "unlinked"])
async def test_an_invite_dies_with_its_issuer_ownership(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    loss: str,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    residents = ResidentsRepo(session)
    issuer = await residents.get_for_house(own.user_id, own.house_id)
    assert issuer is not None
    if loss == "revoked":
        await residents.revoke_verification(issuer)
    elif loss == "blocked":
        await residents.set_status(issuer, ResidentStatus.BLOCKED, "долг")
    else:
        await residents.delete(issuer)

    with pytest.raises(InvalidState, match=INVITE_ISSUER_GONE):
        await service.activate_invite(await add_user(session), invite.code)
    unused = await InvitesRepo(session).get_flat(invite.code)
    assert unused is not None
    assert unused.activations_used == 0


async def test_a_revoked_owner_cannot_verify_the_flat_again(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, ACCOUNT)
    resident = await _add_resident(
        session,
        own.user_id,
        own.house_id,
        own.flat_id,
        verified=True,
    )
    await ResidentsRepo(session).revoke_verification(resident)

    with pytest.raises(NotEnoughRights, match=REVOKED_BY_ORG):
        await _make_service(session).verify(own.user_id, own.flat_id, ACCOUNT)


async def test_a_revoked_resident_cannot_return_by_an_invite(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    revoked_id = await add_user(session)
    revoked = await _add_resident(
        session,
        revoked_id,
        own.house_id,
        own.flat_id,
        verified=True,
    )
    residents = ResidentsRepo(session)
    await residents.revoke_verification(revoked)
    await residents.delete(revoked)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)

    with pytest.raises(NotEnoughRights, match=REVOKED_BY_ORG):
        await service.activate_invite(revoked_id, invite.code)


async def test_verify_attempts_past_the_hourly_quota_are_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, ACCOUNT)
    resident = await _add_resident(session, own.user_id, own.house_id, None)
    residency = CurrentResidency(
        user_id=own.user_id,
        house_id=own.house_id,
        flat_id=None,
        can_see_charges=True,
        verified=False,
    )
    service = _make_service(session)
    quota = VerifyQuota()
    for number in range(VERIFY_CALLS):
        wrong = VerifyFlatRequest(account_no=f"{number:010}")
        result = await verify_flat(own.flat_id, residency, service, wrong, quota)
        assert result.verified is False

    right = VerifyFlatRequest(account_no=ACCOUNT)
    with pytest.raises(TooManyRequests):
        await verify_flat(own.flat_id, residency, service, right, quota)
    by_qr = VerifyFlatByQrRequest(payment_qr=_payment_qr(ACCOUNT))
    with pytest.raises(TooManyRequests):
        await verify_flat(own.flat_id, residency, service, by_qr, quota)
    assert resident.verified_at is None


def _payment_qr(pers_acc: str) -> str:
    return f"ST00012|Name=Демо-УК|PayeeINN=9900000001|persAcc={pers_acc}|Sum=150000"


async def test_verify_by_qr_takes_the_account_from_the_receipt(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, "0000000012")
    resident = await _add_resident(session, own.user_id, own.house_id, None)

    result = await _make_service(session).verify_by_qr(
        own.user_id,
        own.flat_id,
        _payment_qr("0000000012"),
    )

    assert result.verified is True
    assert resident.flat_id == own.flat_id
    assert resident.verified_at is not None
    [requested] = await events_of(session, EventType.FLAT_VERIFICATION_REQUESTED)
    [verified] = await events_of(session, EventType.FLAT_VERIFIED)
    assert requested.payload["method"] == "qr"
    assert verified.payload["by"] == "qr"


async def test_verify_by_qr_of_another_flat_is_a_mismatch(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, "0000000012")
    resident = await _add_resident(session, own.user_id, own.house_id, None)

    result = await _make_service(session).verify_by_qr(
        own.user_id,
        own.flat_id,
        _payment_qr("0000000013"),
    )

    assert result.verified is False
    assert result.detail == MISMATCH_DETAIL
    assert resident.verified_at is None


@pytest.mark.parametrize(
    "payment_qr",
    ["https://vkmax.k1rles.ru/", "ST00012|Name=Демо-УК|PayeeINN=9900000001"],
)
async def test_verify_by_qr_refuses_a_qr_without_an_account(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    payment_qr: str,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, "0000000012")
    resident = await _add_resident(session, own.user_id, own.house_id, None)

    with pytest.raises(InvalidRequest, match=NOT_PAYMENT_QR):
        await _make_service(session).verify_by_qr(
            own.user_id,
            own.flat_id,
            payment_qr,
        )
    assert resident.verified_at is None
    assert await FlatsRepo(session).get_latest_request(own.user_id, own.flat_id) is None


async def test_verify_by_qr_refuses_a_tenant_as_manual_input_does(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, "0000000012")
    await _add_resident(
        session,
        own.user_id,
        own.house_id,
        own.flat_id,
        ResidentRole.TENANT,
    )

    with pytest.raises(NotEnoughRights, match="собственник"):
        await _make_service(session).verify_by_qr(
            own.user_id,
            own.flat_id,
            _payment_qr("0000000012"),
        )


async def _let(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    publisher: TaskPublisher | None = None,
) -> tuple[OrgHouseFlatUser, Resident, FlatsService, str]:
    own = await _verified_owner(session, make_org_house_flat_user)
    service = _make_service(session, publisher)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 2)
    view = await service.activate_invite(await add_user(session), invite.code)
    return own, view.resident, service, invite.code


async def test_ending_a_tenancy_removes_the_tenant_and_their_code(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    own, tenant, service, code = await _let(
        session,
        make_org_house_flat_user,
        publisher,
    )
    tenant_id = tenant.user_id

    await service.end_tenancy(own.user_id, own.flat_id, tenant.id)

    residents = ResidentsRepo(session)
    assert await residents.get_for_house(tenant_id, own.house_id) is None
    [tenancy] = await residents.list_tenancies(own.flat_id)
    assert tenancy.user_id == tenant_id
    assert tenancy.ended_at is not None
    assert tenancy.ended_by == own.user_id
    with pytest.raises(InvalidState):
        await service.activate_invite(tenant_id, code)
    [ended] = await events_of(session, EventType.TENANCY_ENDED)
    assert ended.payload["tenant_id"] == tenant_id
    await publisher.flush()
    [sent] = broker.enqueued(TaskName.SEND_TO_USER)
    assert sent["user_id"] == tenant_id
    assert sent["mandatory"] is True
    assert "завершил аренду" in sent["text"]


async def test_an_ended_tenant_returns_by_a_new_code(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, tenant, service, _code = await _let(session, make_org_house_flat_user)
    await service.end_tenancy(own.user_id, own.flat_id, tenant.id)
    fresh = await service.create_invite(own.user_id, own.flat_id, 72, 1)

    back = await service.activate_invite(tenant.user_id, fresh.code)

    assert back.resident.role is ResidentRole.TENANT
    assert back.resident.verified_at is not None
    history = await service.tenancies(own.user_id, own.flat_id)
    assert [view.tenancy.ended_at is None for view in history] == [True, False]


@pytest.mark.parametrize("actor", ["tenant", "unverified_owner", "neighbour"])
async def test_only_a_verified_owner_of_the_flat_ends_a_tenancy(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    actor: str,
) -> None:
    own, tenant, service, code = await _let(session, make_org_house_flat_user)
    actor_id = await add_user(session)
    if actor == "tenant":
        await service.activate_invite(actor_id, code)
    elif actor == "unverified_owner":
        await _add_resident(session, actor_id, own.house_id, own.flat_id)
    else:
        neighbour_flat = await _add_flat(session, own.house_id, "2")
        await _add_resident(
            session,
            actor_id,
            own.house_id,
            neighbour_flat,
            verified=True,
        )

    with pytest.raises(NotEnoughRights):
        await service.end_tenancy(actor_id, own.flat_id, tenant.id)
    with pytest.raises(NotEnoughRights):
        await service.tenancies(actor_id, own.flat_id)
    assert await ResidentsRepo(session).get(tenant.id) is not None


async def test_an_owner_cannot_end_a_tenant_of_another_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, tenant, service, _code = await _let(session, make_org_house_flat_user)
    neighbour_flat = await _add_flat(session, own.house_id, "2")
    neighbour = await add_user(session)
    await _add_resident(session, neighbour, own.house_id, neighbour_flat, verified=True)

    with pytest.raises(EntityNotFound):
        await service.end_tenancy(neighbour, neighbour_flat, tenant.id)
    assert await ResidentsRepo(session).get(tenant.id) is not None


@pytest.mark.parametrize("target", ["self", "co_owner"])
async def test_ending_a_tenancy_never_removes_an_owner(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    target: str,
) -> None:
    own = await _verified_owner(session, make_org_house_flat_user)
    residents = ResidentsRepo(session)
    if target == "self":
        owner = await residents.get_for_house(own.user_id, own.house_id)
        assert owner is not None
    else:
        owner = await _add_resident(
            session,
            await add_user(session),
            own.house_id,
            own.flat_id,
            verified=True,
        )

    with pytest.raises(NotEnoughRights, match=NOT_A_TENANT):
        await _make_service(session).end_tenancy(own.user_id, own.flat_id, owner.id)
    assert await residents.get(owner.id) is not None


async def test_a_tenant_blocked_by_the_org_is_not_released_by_the_owner(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, tenant, service, _code = await _let(session, make_org_house_flat_user)
    await ResidentsRepo(session).set_status(tenant, ResidentStatus.BLOCKED, "долг")

    with pytest.raises(InvalidState, match=TENANT_BLOCKED):
        await service.end_tenancy(own.user_id, own.flat_id, tenant.id)
    assert await ResidentsRepo(session).get(tenant.id) is not None


@pytest.mark.parametrize("schema", [VerifyFlatRequest, FlatVerificationRequest])
def test_an_account_number_is_capped_in_length(
    schema: type[VerifyFlatRequest | FlatVerificationRequest],
) -> None:
    schema(account_no="1" * ACCOUNT_NO_MAX_LENGTH)

    with pytest.raises(ValidationError):
        schema(account_no="1" * (ACCOUNT_NO_MAX_LENGTH + 1))
