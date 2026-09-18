from collections.abc import Sequence
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, Header

from zheka.api.dependencies.current_account import CurrentAccountDep
from zheka.base import ZhekaType
from zheka.core.enums import ResidentRole, ResidentStatus
from zheka.core.errors import EntityNotFound, NotEnoughRights
from zheka.core.ids import FlatId, HouseId, ResidentId, UserId
from zheka.infra.database.models import Resident
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.residents import ResidentsRepo

BLOCKED = "УК закрыла вам доступ к этому дому"
FLAT_NOT_FOUND = "Квартира не найдена"
HOUSE_NOT_FOUND = "Дом не найден"


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


def blocked_detail(reason: str | None) -> str:
    # причина из residents.block_reason: отказ без нее не подсказывает жителю,
    # к кому идти и что исправлять
    return BLOCKED if reason is None else f"{BLOCKED}: {reason}"


def residency_of(resident: Resident | None, not_found: str) -> CurrentResidency:
    # чужой дом и чужая квартира отвечают 404, потому что 403 подтвердил бы,
    # что такой id есть. Заблокированный житель - обратный случай: он и так
    # знает, что дом существует, его оттуда выселила УК, и молчаливый 404
    # вместо прямого отказа был бы худшим ответом
    if resident is None:
        raise EntityNotFound(not_found)
    if resident.status is ResidentStatus.BLOCKED:
        raise NotEnoughRights(blocked_detail(resident.block_reason))
    return _to_residency(resident)


def resolve_residency(
    residencies: Sequence[Resident],
    house_id_header: HouseId | None,
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
    # подтверждение квартиры и есть тот момент, когда residents.flat_id
    # проставляется, поэтому доступ сюда дает дом квартиры, а не сама
    # квартира: иначе житель, пришедший по диплинку дома, не дошел бы никогда
    flat = await houses_repo.get_flat(flat_id)
    if flat is None:
        raise EntityNotFound(FLAT_NOT_FOUND)
    resident = await residents_repo.get_for_house(
        current_account.user_id,
        HouseId(flat.house_id),
    )
    return residency_of(resident, FLAT_NOT_FOUND)


ResidencyForHouseDep = Annotated[CurrentResidency, Depends(residency_for)]
ResidencyForFlatDep = Annotated[CurrentResidency, Depends(residency_for_flat)]
ResidencyForFlatHouseDep = Annotated[
    CurrentResidency,
    Depends(residency_for_flat_house),
]
