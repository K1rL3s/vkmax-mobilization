import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, cast

import pytest
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
from zheka.core.enums import ResidentRole, ResidentStatus, VerificationStatus
from zheka.core.errors import EntityNotFound, NotEnoughRights
from zheka.core.ids import FlatId, HouseId, MaxUserId, UserId
from zheka.core.services.profile import ProfileService
from zheka.core.texts import BLOCKED
from zheka.infra.database.models import Resident
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

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
    )


def _original(dependency: Any) -> Callable[..., Awaitable[CurrentResidency]]:
    # @inject вырезает параметры FromDishka из сигнатуры обертки, поэтому
    # тест зовет оригинал и передает репозитории руками
    return cast(
        Callable[..., Awaitable[CurrentResidency]],
        dependency.__dishka_orig_func__,
    )


def _account(user_id: UserId) -> CurrentAccount:
    return CurrentAccount(
        user_id=user_id,
        max_user_id=MaxUserId(secrets.randbits(48)),
        name="Житель",
        consent_at=None,
    )


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


def test_resolve_residency_refuses_a_blocked_resident() -> None:
    resident = Resident(
        user_id=UserId(1),
        house_id=HouseId(1),
        role=ResidentRole.OWNER,
        status=ResidentStatus.BLOCKED,
        block_reason=BLOCK_REASON,
    )

    with pytest.raises(NotEnoughRights) as refused:
        resolve_residency([resident], None)

    assert BLOCK_REASON in str(refused.value)


def test_resolve_residency_refuses_a_blocked_resident_without_a_reason() -> None:
    resident = Resident(
        user_id=UserId(1),
        house_id=HouseId(1),
        role=ResidentRole.OWNER,
        status=ResidentStatus.BLOCKED,
    )

    with pytest.raises(NotEnoughRights) as refused:
        resolve_residency([resident], None)

    assert str(refused.value) == BLOCKED


def test_resolve_residency_passes_an_active_resident() -> None:
    resident = Resident(
        user_id=UserId(1),
        house_id=HouseId(7),
        role=ResidentRole.OWNER,
    )

    assert resolve_residency([resident], None).house_id == 7


async def test_residency_for_refuses_a_blocked_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights) as refused:
        await _original(residency_for)(
            house_id=own.house_id,
            current_account=_account(own.user_id),
            residents_repo=ResidentsRepo(session),
        )

    assert BLOCK_REASON in str(refused.value)


async def test_residency_for_answers_not_found_for_a_foreign_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)

    # 403 подтвердил бы, что дом с таким id есть
    with pytest.raises(EntityNotFound):
        await _original(residency_for)(
            house_id=foreign.house_id,
            current_account=_account(own.user_id),
            residents_repo=ResidentsRepo(session),
        )


async def test_residency_for_flat_refuses_a_blocked_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights) as refused:
        await _original(residency_for_flat)(
            flat_id=own.flat_id,
            current_account=_account(own.user_id),
            residents_repo=ResidentsRepo(session),
        )

    assert BLOCK_REASON in str(refused.value)


async def test_residency_for_flat_answers_not_found_for_a_foreign_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)

    with pytest.raises(EntityNotFound):
        await _original(residency_for_flat)(
            flat_id=foreign.flat_id,
            current_account=_account(own.user_id),
            residents_repo=ResidentsRepo(session),
        )


async def test_residency_for_flat_house_refuses_a_blocked_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _block(session, own.user_id, own.house_id)

    with pytest.raises(NotEnoughRights) as refused:
        await _original(residency_for_flat_house)(
            flat_id=own.flat_id,
            current_account=_account(own.user_id),
            residents_repo=ResidentsRepo(session),
            houses_repo=HousesRepo(session),
        )

    assert BLOCK_REASON in str(refused.value)


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

    # блокировка живет на жительстве, а не на аккаунте
    residency = await _original(residency_for)(
        house_id=other.house_id,
        current_account=_account(blocked_house.user_id),
        residents_repo=ResidentsRepo(session),
    )

    assert residency.house_id == other.house_id


async def test_get_me_still_lists_a_blocked_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _block(session, own.user_id, own.house_id)
    profile_service = _profile_service(session)

    # свитчер - единственный экран, который заблокированный обязан видеть:
    # иначе приложение пустое и без объяснения
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


async def test_get_me_leaves_the_verification_status_empty_without_a_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)

    view = await _profile_service(session).me(own.user_id)

    summary = ResidencySummary.of(view.residencies[0])
    assert summary.verification_status is None
    assert summary.verification_reject_reason is None


async def test_get_me_carries_the_pending_verification_status(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _request_verification(session, own.user_id, own.flat_id)

    view = await _profile_service(session).me(own.user_id)

    summary = ResidencySummary.of(view.residencies[0])
    assert summary.verification_status is VerificationStatus.PENDING
    assert summary.verification_reject_reason is None


async def test_get_me_carries_the_reject_reason(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _request_verification(
        session,
        own.user_id,
        own.flat_id,
        VerificationStatus.REJECTED,
        REJECT_REASON,
    )

    view = await _profile_service(session).me(own.user_id)

    summary = ResidencySummary.of(view.residencies[0])
    assert summary.verification_status is VerificationStatus.REJECTED
    assert summary.verification_reject_reason == REJECT_REASON


async def test_get_me_hides_the_note_of_an_approved_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    await _request_verification(
        session,
        own.user_id,
        own.flat_id,
        VerificationStatus.APPROVED,
        "Проверено по реестру",
    )

    view = await _profile_service(session).me(own.user_id)

    summary = ResidencySummary.of(view.residencies[0])
    assert summary.verification_status is VerificationStatus.APPROVED
    assert summary.verification_reject_reason is None


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
    # запрос по свободному номеру квартиры завести не за что: карточки нет
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

    # мультидом - обычный случай, и один запрос в базу разводит квартиры сам
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
