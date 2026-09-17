import secrets
from collections.abc import Awaitable, Callable
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser

from zheka.api.dependencies.current_account import CurrentAccount
from zheka.api.dependencies.current_residency import (
    BLOCKED,
    CurrentResidency,
    residency_for,
    residency_for_flat,
    residency_for_flat_house,
    resolve_residency,
)
from zheka.core.enums import ResidentRole, ResidentStatus
from zheka.core.errors import EntityNotFound, NotEnoughRights
from zheka.core.ids import HouseId, MaxUserId, UserId
from zheka.core.services.profile import ProfileService
from zheka.infra.database.models import Resident
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

BLOCK_REASON = "Задолженность по коммунальным услугам"

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


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
    profile_service = ProfileService(
        UsersRepo(session),
        ResidentsRepo(session),
        HousesRepo(session),
        OrgsRepo(session),
    )

    # свитчер - единственный экран, который заблокированный обязан видеть:
    # иначе приложение пустое и без объяснения
    view = await profile_service.me(own.user_id)

    assert [residency.house.id for residency in view.residencies] == [own.house_id]
    assert view.residencies[0].resident.status is ResidentStatus.BLOCKED
    assert view.residencies[0].resident.block_reason == BLOCK_REASON
