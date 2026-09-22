import inspect
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser

from zheka.api.dependencies.current_account import CurrentAccount
from zheka.api.dependencies.current_residency import (
    CurrentResidency,
    residency_for,
    residency_for_flat,
    residency_for_flat_house,
    resolve_residency,
)
from zheka.api.schemas.houses import ResidencySummary
from zheka.core.consent import CONSENT_VERSION
from zheka.core.enums import (
    EventSource,
    EventType,
    ResidentRole,
    ResidentStatus,
    VerificationStatus,
)
from zheka.core.errors import EntityNotFound, NotEnoughRights
from zheka.core.ids import FlatId, HouseId, MaxUserId, UserId
from zheka.core.services.events import EventsService
from zheka.core.services.profile import ProfileService
from zheka.core.texts import BLOCKED
from zheka.infra.database.models import Resident
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.events import events_table

BLOCK_REASON = "Задолженность по коммунальным услугам"
REJECT_REASON = "Лицевой счет принадлежит другой квартире"

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


def _profile_service(session: AsyncSession) -> ProfileService:
    return ProfileService(
        UsersRepo(session),
        ResidentsRepo(session),
        HousesRepo(session),
        OrgsRepo(session),
        FlatsRepo(session),
        EventsService(EventsRepo(session)),
    )


def _account(user_id: UserId) -> CurrentAccount:
    return CurrentAccount(
        user_id=user_id,
        max_user_id=MaxUserId(secrets.randbits(48)),
        name="Житель",
        consent_at=None,
    )


async def _resolve(
    session: AsyncSession,
    dependency: Any,
    user_id: UserId,
    house_id: HouseId,
    flat_id: FlatId,
) -> CurrentResidency:
    original = dependency.__dishka_orig_func__
    arguments = {
        "house_id": house_id,
        "flat_id": flat_id,
        "current_account": _account(user_id),
        "residents_repo": ResidentsRepo(session),
        "houses_repo": HousesRepo(session),
    }
    wanted = inspect.signature(original).parameters
    result: CurrentResidency = await original(
        **{name: value for name, value in arguments.items() if name in wanted},
    )
    return result


async def _block(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    reason: str | None = BLOCK_REASON,
) -> None:
    residents_repo = ResidentsRepo(session)
    resident = await residents_repo.get_for_house(user_id, house_id)
    assert resident is not None
    await residents_repo.set_status(resident, ResidentStatus.BLOCKED, reason)


@pytest.mark.parametrize(
    ("reason", "detail"),
    [(BLOCK_REASON, f"{BLOCKED}: {BLOCK_REASON}"), (None, BLOCKED)],
    ids=["reason", "no-reason"],
)
def test_resolve_residency_refuses_a_blocked_resident(
    reason: str | None,
    detail: str,
) -> None:
    resident = Resident(
        user_id=UserId(1),
        house_id=HouseId(1),
        role=ResidentRole.OWNER,
        status=ResidentStatus.BLOCKED,
        block_reason=reason,
    )

    with pytest.raises(NotEnoughRights) as refused:
        resolve_residency([resident], None)

    assert str(refused.value) == detail


DEPENDENCIES = [residency_for, residency_for_flat, residency_for_flat_house]


@pytest.mark.parametrize("dependency", DEPENDENCIES)
async def test_a_residency_dependency_refuses_a_blocked_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    dependency: Any,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights) as refused:
        await _resolve(session, dependency, own.user_id, own.house_id, own.flat_id)

    assert BLOCK_REASON in str(refused.value)


@pytest.mark.parametrize("dependency", DEPENDENCIES)
async def test_a_residency_dependency_answers_not_found_for_a_foreign_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    dependency: Any,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)

    with pytest.raises(EntityNotFound):
        await _resolve(
            session,
            dependency,
            own.user_id,
            foreign.house_id,
            foreign.flat_id,
        )


async def test_blocked_in_one_house_keeps_the_other_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    blocked_house = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    other = await make_org_house_flat_user()
    session.add(
        Resident(
            user_id=blocked_house.user_id,
            house_id=other.house_id,
            flat_id=other.flat_id,
            role=ResidentRole.OWNER,
        ),
    )
    await session.flush()
    await _block(session, blocked_house.user_id, blocked_house.house_id)

    residency = await _resolve(
        session,
        residency_for,
        blocked_house.user_id,
        other.house_id,
        other.flat_id,
    )

    assert residency.house_id == other.house_id


async def test_get_me_still_lists_a_blocked_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _block(session, own.user_id, own.house_id)
    profile_service = _profile_service(session)

    view = await profile_service.me(own.user_id)

    assert [residency.house.id for residency in view.residencies] == [own.house_id]
    assert view.residencies[0].resident.status is ResidentStatus.BLOCKED
    assert view.residencies[0].resident.block_reason == BLOCK_REASON


async def _request_verification(
    session: AsyncSession,
    user_id: UserId,
    flat_id: FlatId,
    status: VerificationStatus = VerificationStatus.PENDING,
    reason: str | None = None,
) -> None:
    flats_repo = FlatsRepo(session)
    request = await flats_repo.add_verification_request(flat_id, user_id, "ЛС-1", None)
    assert request is not None
    if status is not VerificationStatus.PENDING:
        await flats_repo.decide_verification_request(
            request,
            status,
            user_id,
            datetime.now(UTC),
            reason,
        )


@pytest.mark.parametrize(
    ("status", "reason", "shown_reason"),
    [
        (None, None, None),
        (VerificationStatus.PENDING, None, None),
        (VerificationStatus.REJECTED, REJECT_REASON, REJECT_REASON),
        (VerificationStatus.APPROVED, "Проверено по реестру", None),
    ],
)
async def test_get_me_carries_the_verification_status(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    status: VerificationStatus | None,
    reason: str | None,
    shown_reason: str | None,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    if status is not None:
        await _request_verification(session, own.user_id, own.flat_id, status, reason)

    view = await _profile_service(session).me(own.user_id)

    summary = ResidencySummary.of(view.residencies[0])
    assert summary.verification_status is status
    assert summary.verification_reject_reason == shown_reason


async def test_get_me_leaves_the_status_empty_for_a_residency_without_a_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    session.add(
        Resident(
            user_id=own.user_id,
            house_id=own.house_id,
            role=ResidentRole.OWNER,
            flat_number="12",
        ),
    )
    await session.flush()
    await _request_verification(session, own.user_id, own.flat_id)

    view = await _profile_service(session).me(own.user_id)

    summary = ResidencySummary.of(view.residencies[0])
    assert summary.flat_id is None
    assert summary.verification_status is None
    assert summary.verification_reject_reason is None


async def test_get_me_keeps_each_residency_on_its_own_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    pending = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    rejected = await make_org_house_flat_user()
    session.add(
        Resident(
            user_id=pending.user_id,
            house_id=rejected.house_id,
            flat_id=rejected.flat_id,
            role=ResidentRole.OWNER,
        ),
    )
    await session.flush()
    await _request_verification(session, pending.user_id, pending.flat_id)
    await _request_verification(
        session,
        pending.user_id,
        rejected.flat_id,
        VerificationStatus.REJECTED,
        REJECT_REASON,
    )

    view = await _profile_service(session).me(pending.user_id)

    statuses = {
        residency.flat.id: residency.verification_status
        for residency in view.residencies
        if residency.flat is not None
    }
    assert statuses == {
        pending.flat_id: VerificationStatus.PENDING,
        rejected.flat_id: VerificationStatus.REJECTED,
    }


async def test_a_consent_is_recorded_with_its_source(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    ids = await make_org_house_flat_user()

    await _profile_service(session).accept_consent(
        ids.user_id,
        CONSENT_VERSION,
        EventSource.MINIAPP,
    )

    stmt = select(events_table.c.payload).where(
        events_table.c.type == EventType.CONSENT_GIVEN,
        events_table.c.user_id == ids.user_id,
    )
    assert (await session.execute(stmt)).scalars().all() == [
        {"source": EventSource.MINIAPP.value, "version": CONSENT_VERSION},
    ]
