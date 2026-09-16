from collections.abc import Sequence
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, Header

from zheka.api.dependencies.current_account import CurrentAccountDep
from zheka.base import ZhekaType
from zheka.core.enums import ResidentRole, ResidentStatus
from zheka.core.errors import NotEnoughRights
from zheka.core.ids import FlatId, HouseId, ResidentId, UserId
from zheka.infra.database.models import Resident
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


def _to_residency(resident: Resident) -> CurrentResidency:
    return CurrentResidency(
        resident_id=ResidentId(resident.id),
        user_id=UserId(resident.user_id),
        house_id=HouseId(resident.house_id),
        flat_id=FlatId(resident.flat_id) if resident.flat_id is not None else None,
        role=resident.role,
        can_see_charges=resident.can_see_charges,
        can_vote=resident.can_vote,
        status=resident.status,
        verified=resident.verified_at is not None,
        is_chairman=resident.is_chairman,
    )


def resolve_residency(
    residencies: Sequence[Resident],
    house_id_header: int | None,
) -> CurrentResidency:
    if not residencies:
        raise NotEnoughRights("Вы не житель ни одного дома")
    resident: Resident
    if house_id_header is None:
        if len(residencies) > 1:
            raise NotEnoughRights(
                "Укажите X-House-Id: вы житель нескольких домов",
            )
        resident = residencies[0]
    else:
        found = next(
            (r for r in residencies if r.house_id == house_id_header),
            None,
        )
        if found is None:
            raise NotEnoughRights("Нет доступа к этому дому")
        resident = found
    return _to_residency(resident)


@inject
async def get_current_residency(
    *,
    current_account: CurrentAccountDep,
    residents_repo: FromDishka[ResidentsRepo],
    house_id_header: Annotated[int | None, Header(alias="X-House-Id")] = None,
) -> CurrentResidency:
    residencies = await residents_repo.list_for_user(current_account.user_id)
    return resolve_residency(residencies, house_id_header)


CurrentResidencyDep = Annotated[CurrentResidency, Depends(get_current_residency)]


@inject
async def residency_for(
    *,
    house_id: int,
    current_account: CurrentAccountDep,
    residents_repo: FromDishka[ResidentsRepo],
) -> CurrentResidency:
    resident = await residents_repo.get_for_house(
        current_account.user_id,
        HouseId(house_id),
    )
    if resident is None:
        raise NotEnoughRights("Вы не житель этого дома")
    return _to_residency(resident)


@inject
async def residency_for_flat(
    *,
    flat_id: int,
    current_account: CurrentAccountDep,
    residents_repo: FromDishka[ResidentsRepo],
) -> CurrentResidency:
    residents = await residents_repo.list_for_flat(FlatId(flat_id))
    resident = next(
        (r for r in residents if r.user_id == current_account.user_id),
        None,
    )
    if resident is None:
        raise NotEnoughRights("Вы не житель этой квартиры")
    return _to_residency(resident)
