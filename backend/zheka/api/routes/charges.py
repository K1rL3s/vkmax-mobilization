from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import (
    CurrentResidency,
    RequireConsentDep,
    ResidencyForFlatDep,
    ResidencyForHouseDep,
)
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.api.schemas.charges import (
    ChargeBreakdown,
    ChargeCard,
    ChargeListItem,
    DisputeChargeRequest,
    DisputeChargeResponse,
    PayChargeResponse,
    TariffItem,
)
from zheka.api.schemas.files import FileRef
from zheka.core.errors import NotEnoughRights
from zheka.core.ids import ChargeId, FlatId, HouseId
from zheka.core.services.charges import CANNOT_SEE_CHARGES, NOT_VERIFIED, ChargesService
from zheka.core.services.files import FilesService

router = APIRouter(tags=["Начисления"], route_class=DishkaRoute)


def _require_can_see_charges(residency: CurrentResidency) -> None:
    if not residency.verified:
        raise NotEnoughRights(NOT_VERIFIED)
    if not residency.can_see_charges:
        raise NotEnoughRights(CANNOT_SEE_CHARGES)


@router.get("/houses/{house_id}/tariffs", summary="Тарифы дома")
async def list_house_tariffs(
    house_id: HouseId,
    residency: ResidencyForHouseDep,  # noqa: ARG001
    charges_service: FromDishka[ChargesService],
    files_service: FromDishka[FilesService],
) -> list[TariffItem]:
    tariffs = await charges_service.tariffs(house_id)
    return [
        TariffItem.of(
            tariff,
            (
                None
                if tariff.document_url is None
                else FileRef(
                    name=tariff.document_url,
                    url=files_service.sign(tariff.document_url),
                )
            ),
        )
        for tariff in tariffs
    ]


@router.get("/flats/{flat_id}/charges", summary="Начисления квартиры")
async def list_flat_charges(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    charges_service: FromDishka[ChargesService],
    limit: Limit = 12,
    offset: Offset = 0,
) -> Page[ChargeListItem]:
    _require_can_see_charges(residency)
    charges, total = await charges_service.list_for_flat(flat_id, limit, offset)
    return Page(
        items=[ChargeListItem.model_validate(charge) for charge in charges], total=total
    )


@router.get("/charges/{charge_id}", summary="Квитанция за период")
async def get_charge(
    charge_id: ChargeId,
    current_account: RequireConsentDep,
    charges_service: FromDishka[ChargesService],
) -> ChargeCard:
    data = await charges_service.card(charge_id, current_account.user_id)
    return ChargeCard.of_card(data)


@router.get("/charges/{charge_id}/breakdown", summary="Разбор начисления")
async def get_charge_breakdown(
    charge_id: ChargeId,
    current_account: RequireConsentDep,
    charges_service: FromDishka[ChargesService],
) -> ChargeBreakdown:
    data = await charges_service.breakdown(charge_id, current_account.user_id)
    return ChargeBreakdown.of(data)


@router.post("/charges/{charge_id}/dispute", summary="Оспорить начисление")
async def dispute_charge(
    charge_id: ChargeId,
    current_account: RequireConsentDep,
    charges_service: FromDishka[ChargesService],
    body: DisputeChargeRequest,
) -> DisputeChargeResponse:
    request_id = await charges_service.dispute(
        charge_id, current_account.user_id, body.comment, body.service
    )
    return DisputeChargeResponse(request_id=request_id)


@router.post("/charges/{charge_id}/pay", summary="Демо-оплата квитанции")
async def pay_charge_demo(
    charge_id: ChargeId,
    current_account: RequireConsentDep,
    charges_service: FromDishka[ChargesService],
) -> PayChargeResponse:
    result = await charges_service.pay_demo(charge_id, current_account.user_id)
    return PayChargeResponse(charge_id=result.charge_id, paid_at=result.paid_at)
