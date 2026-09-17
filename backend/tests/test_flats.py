import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser

from zheka.api.schemas.flats import FlatCard
from zheka.core.enums import OrgRole, ResidentRole, VerificationStatus
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import FlatId, HouseId, MaxUserId, UserId
from zheka.core.services.events import EventsService
from zheka.core.services.flats import ALREADY_VERIFIED_DETAIL, FlatsService
from zheka.infra.database.models import Flat, Resident, User, VerificationRequest
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.invites import InvitesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

ACCOUNT = "ЛС-0042 7781"

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


def _make_service(session: AsyncSession) -> FlatsService:
    return FlatsService(
        FlatsRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        InvitesRepo(session),
        UsersRepo(session),
        OrgsRepo(session),
        EventsService(EventsRepo(session)),
    )


async def _add_user(session: AsyncSession) -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name="Житель")
    session.add(user)
    await session.flush()
    return UserId(user.id)


async def _add_flat(
    session: AsyncSession,
    house_id: HouseId,
    number: str,
    account_no: str | None = None,
) -> FlatId:
    flat = Flat(house_id=house_id, number=number, account_no=account_no)
    session.add(flat)
    await session.flush()
    return FlatId(flat.id)


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


async def test_verify_matches_the_account_ignoring_spaces_and_case(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, ACCOUNT)
    # житель пришел по диплинку дома, квартиры у него еще нет
    resident = await _add_resident(session, own.user_id, own.house_id, None)

    result = await _make_service(session).verify(
        own.user_id,
        own.flat_id,
        " лс-0042  7781 ",
    )

    assert result.verified is True
    assert resident.flat_id == own.flat_id
    assert resident.verified_at is not None
    # самообслуживание, подтвердившего сотрудника нет
    assert resident.verified_by is None


async def test_verify_with_a_wrong_account_creates_nothing(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, ACCOUNT)
    resident = await _add_resident(session, own.user_id, own.house_id, None)

    result = await _make_service(session).verify(own.user_id, own.flat_id, "0000")

    assert result.verified is False
    assert resident.flat_id is None
    assert resident.verified_at is None


async def test_verify_never_matches_a_flat_without_an_account(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    resident = await _add_resident(session, own.user_id, own.house_id, None)

    result = await _make_service(session).verify(own.user_id, own.flat_id, "")

    assert result.verified is False
    assert resident.verified_at is None


async def test_verify_is_idempotent_on_the_same_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, ACCOUNT)
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)

    result = await _make_service(session).verify(own.user_id, own.flat_id, ACCOUNT)

    assert result.verified is True
    assert result.detail == ALREADY_VERIFIED_DETAIL


async def test_verify_refuses_a_move_to_another_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    other_flat = await _add_flat(session, own.house_id, "2", ACCOUNT)
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)

    with pytest.raises(InvalidState):
        await _make_service(session).verify(own.user_id, other_flat, ACCOUNT)


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


async def test_second_pending_request_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, None)
    service = _make_service(session)
    await service.request_verification(
        own.user_id, own.flat_id, ACCOUNT, "я собственник"
    )

    with pytest.raises(InvalidState):
        await service.request_verification(own.user_id, own.flat_id, ACCOUNT, None)


async def test_request_verification_is_refused_for_a_verified_residency(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)

    with pytest.raises(InvalidState):
        await _make_service(session).request_verification(
            own.user_id,
            own.flat_id,
            ACCOUNT,
            None,
        )


async def test_approve_verifies_the_resident_and_closes_the_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    staff = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    resident = await _add_resident(
        session, await _add_user(session), staff.house_id, None
    )
    request = await _add_request(session, staff.flat_id, UserId(resident.user_id))
    service = _make_service(session)

    view = await service.approve_verification(staff.org_id, request.id, staff.user_id)

    assert view.request.status is VerificationStatus.APPROVED
    assert view.request.decided_by == staff.user_id
    assert view.request.decided_at is not None
    assert resident.flat_id == staff.flat_id
    assert resident.verified_by == staff.user_id


async def test_deciding_a_decided_request_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    staff = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    resident = await _add_resident(
        session, await _add_user(session), staff.house_id, None
    )
    request = await _add_request(session, staff.flat_id, UserId(resident.user_id))
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
    staff = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    resident = await _add_resident(
        session, await _add_user(session), staff.house_id, None
    )
    request = await _add_request(session, staff.flat_id, UserId(resident.user_id))

    with pytest.raises(InvalidRequest):
        await _make_service(session).reject_verification(
            staff.org_id,
            request.id,
            staff.user_id,
            reason,
        )

    assert request.status is VerificationStatus.PENDING


async def test_reject_stores_the_reason(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    staff = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    resident = await _add_resident(
        session, await _add_user(session), staff.house_id, None
    )
    request = await _add_request(session, staff.flat_id, UserId(resident.user_id))

    view = await _make_service(session).reject_verification(
        staff.org_id,
        request.id,
        staff.user_id,
        "  счет не ваш  ",
    )

    assert view.request.status is VerificationStatus.REJECTED
    assert view.request.reason == "счет не ваш"
    assert resident.verified_at is None


async def test_foreign_verification_request_is_not_found_for_another_org(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    request = await _add_request(session, other.flat_id, other.user_id)

    # чужой запрос - это 404, а не 403: 403 подтвердил бы, что такой
    # verification_id существует
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


async def test_create_invite_refuses_a_tenant(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(
        session,
        own.user_id,
        own.house_id,
        own.flat_id,
        ResidentRole.TENANT,
        verified=True,
    )

    with pytest.raises(NotEnoughRights):
        await _make_service(session).create_invite(own.user_id, own.flat_id, 72, 1)


async def test_create_invite_refuses_an_unverified_owner(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)

    with pytest.raises(NotEnoughRights):
        await _make_service(session).create_invite(own.user_id, own.flat_id, 72, 1)


@pytest.mark.parametrize(
    ("expires_in_hours", "max_activations"),
    [(0, 1), (-1, 1), (72, 0), (72, -1)],
)
async def test_create_invite_rejects_dead_limits(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    expires_in_hours: int,
    max_activations: int,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)

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
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    tenant_id = await _add_user(session)

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
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    first = await _add_user(session)
    second = await _add_user(session)
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
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)
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
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    neighbour_flat = await _add_flat(session, own.house_id, "2")
    neighbour = await _add_user(session)
    await _add_resident(session, neighbour, own.house_id, neighbour_flat, verified=True)

    with pytest.raises(InvalidState):
        await service.activate_invite(neighbour, invite.code)

    used = await InvitesRepo(session).get_flat(invite.code)
    assert used is not None
    assert used.activations_used == 0


async def test_revoked_invite_is_not_activated(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    await service.revoke_invite(own.user_id, invite.code)

    with pytest.raises(InvalidState):
        await service.activate_invite(await _add_user(session), invite.code)


async def test_invite_is_not_revoked_by_a_stranger(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    neighbour_flat = await _add_flat(session, own.house_id, "2")
    neighbour = await _add_user(session)
    await _add_resident(session, neighbour, own.house_id, neighbour_flat, verified=True)

    # код не говорит в пути, чьей квартире он принадлежит, поэтому чужой код -
    # это 404
    with pytest.raises(EntityNotFound):
        await service.revoke_invite(neighbour, invite.code)

    alive = await InvitesRepo(session).get_flat(invite.code)
    assert alive is not None
    assert alive.revoked_at is None


async def test_flat_card_shows_the_account_tail_only_to_a_verified_owner(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, ACCOUNT)
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)
    tenant = await _add_user(session)
    await _add_resident(
        session,
        tenant,
        own.house_id,
        own.flat_id,
        ResidentRole.TENANT,
        verified=True,
    )
    service = _make_service(session)

    owner_card = FlatCard.of(await service.flat_card(own.user_id, own.flat_id))
    tenant_card = FlatCard.of(await service.flat_card(tenant, own.flat_id))

    assert owner_card.account_no == ACCOUNT[-4:]
    assert owner_card.residents_count == 2
    assert tenant_card.account_no is None


async def test_flat_card_hides_the_account_from_an_unverified_owner(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _set_account(session, own.flat_id, ACCOUNT)
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)

    card = FlatCard.of(await _make_service(session).flat_card(own.user_id, own.flat_id))

    assert card.verified is False
    assert card.account_no is None


async def test_flat_card_carries_the_latest_verification_status(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    service = _make_service(session)
    await service.request_verification(own.user_id, own.flat_id, ACCOUNT, "  ")

    card = FlatCard.of(await service.flat_card(own.user_id, own.flat_id))
    residents = await service.list_residents(own.user_id, own.flat_id)

    assert card.verification_status is VerificationStatus.PENDING
    assert len(residents) == 1
    assert residents[0].user.id == own.user_id


async def test_flat_card_is_refused_to_a_resident_of_another_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    neighbour_flat = await _add_flat(session, own.house_id, "2")
    neighbour = await _add_user(session)
    await _add_resident(session, neighbour, own.house_id, neighbour_flat, verified=True)

    # сосед по дому - не житель этой квартиры, ее карточка ему закрыта
    with pytest.raises(NotEnoughRights):
        await _make_service(session).flat_card(neighbour, own.flat_id)


async def test_revoked_invite_is_dead_even_for_a_resident_of_the_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)
    service = _make_service(session)
    invite = await service.create_invite(own.user_id, own.flat_id, 72, 1)
    await service.revoke_invite(own.user_id, invite.code)

    # у жителя квартиры активация не списывается, и мертвый код не должен
    # молча отвечать успехом
    with pytest.raises(InvalidState):
        await service.activate_invite(own.user_id, invite.code)


async def test_second_pending_row_is_refused_by_the_database(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, None)
    await _add_request(session, own.flat_id, own.user_id)

    # правило живет в частичном уникальном индексе, а не в чтении перед
    # записью: два параллельных нажатия кнопки прошли бы проверку в питоне оба
    session.add(
        VerificationRequest(
            flat_id=own.flat_id,
            user_id=own.user_id,
            account_no=ACCOUNT,
            status=VerificationStatus.PENDING,
        ),
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_verify_answers_not_found_for_a_flat_of_another_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=True)

    # чужая квартира - это 404, а не 403: 403 подтвердил бы, что такой
    # flat_id существует
    with pytest.raises(EntityNotFound):
        await _make_service(session).verify(own.user_id, other.flat_id, ACCOUNT)
