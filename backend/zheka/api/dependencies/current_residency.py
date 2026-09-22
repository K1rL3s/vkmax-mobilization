from collections.abc import Sequence
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, Header

from zheka.api.dependencies.current_account import CurrentAccountDep
from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.enums import ResidentRole, ResidentStatus
from zheka.core.errors import (
    FLAT_NOT_FOUND,
    HOUSE_NOT_FOUND,
    EntityNotFound,
    NotEnoughRights,
)
from zheka.core.ids import FlatId, HouseId, ResidentId, UserId
from zheka.infra.database.models import Resident
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.residents import ResidentsRepo


class CurrentResidency(ZhekaType):
    resident_id: ResidentId
    user_id: UserId
    house_id: HouseId
    flat_id: FlatId | None
    role: ResidentRole
    can_see_charges: bool
    can_vote: bool
    status: ResidentStatus
    verified: bool
    is_chairman: bool


def residency_of(resident: Resident | None, not_found: str) -> CurrentResidency:
    if resident is None:
        raise EntityNotFound(not_found)
    if resident.status is ResidentStatus.BLOCKED:
        raise NotEnoughRights(texts.blocked_detail(resident.block_reason))
    return CurrentResidency(
        resident_id=resident.id,
        user_id=resident.user_id,
        house_id=resident.house_id,
        flat_id=resident.flat_id,
        role=resident.role,
        can_see_charges=resident.can_see_charges,
        can_vote=resident.can_vote,
        status=resident.status,
        verified=resident.verified_at is not None,
        is_chairman=resident.is_chairman,
    )


def resolve_residency(
    residencies: Sequence[Resident],
    house_id_header: HouseId | None,
) -> CurrentResidency:
    if not residencies:
        raise NotEnoughRights("Вы не житель ни одного дома")
    resident: Resident
    if house_id_header is None:
        if len(residencies) > 1:
            raise NotEnoughRights("Укажите X-House-Id: вы житель нескольких домов")
        resident = residencies[0]
    else:
        found = next((r for r in residencies if r.house_id == house_id_header), None)
        if found is None:
            raise NotEnoughRights("Нет доступа к этому дому")
        resident = found
    return residency_of(resident, HOUSE_NOT_FOUND)


@inject
async def get_current_residency(
    *,
    current_account: CurrentAccountDep,
    residents_repo: FromDishka[ResidentsRepo],
    house_id_header: Annotated[HouseId | None, Header(alias="X-House-Id")] = None,
) -> CurrentResidency:
    residencies = await residents_repo.list_for_user(current_account.user_id)
    return resolve_residency(residencies, house_id_header)


CurrentResidencyDep = Annotated[CurrentResidency, Depends(get_current_residency)]


@inject
async def residency_for(
    *,
    house_id: HouseId,
    current_account: CurrentAccountDep,
    residents_repo: FromDishka[ResidentsRepo],
) -> CurrentResidency:
    resident = await residents_repo.get_for_house(current_account.user_id, house_id)
    return residency_of(resident, HOUSE_NOT_FOUND)


@inject
async def residency_for_flat(
    *,
    flat_id: FlatId,
    current_account: CurrentAccountDep,
    residents_repo: FromDishka[ResidentsRepo],
) -> CurrentResidency:
    residents = await residents_repo.list_for_flat(flat_id)
    resident = next(
        (r for r in residents if r.user_id == current_account.user_id),
        None,
    )
    return residency_of(resident, FLAT_NOT_FOUND)


@inject
async def residency_for_flat_house(
    *,
    flat_id: FlatId,
    current_account: CurrentAccountDep,
    residents_repo: FromDishka[ResidentsRepo],
    houses_repo: FromDishka[HousesRepo],
) -> CurrentResidency:
    flat = await houses_repo.get_flat(flat_id)
    if flat is None:
        raise EntityNotFound(FLAT_NOT_FOUND)
    resident = await residents_repo.get_for_house(
        current_account.user_id,
        flat.house_id,
    )
    return residency_of(resident, FLAT_NOT_FOUND)


ResidencyForHouseDep = Annotated[CurrentResidency, Depends(residency_for)]
ResidencyForFlatDep = Annotated[CurrentResidency, Depends(residency_for_flat)]
ResidencyForFlatHouseDep = Annotated[
    CurrentResidency,
    Depends(residency_for_flat_house),
]
