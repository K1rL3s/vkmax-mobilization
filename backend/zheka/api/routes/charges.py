from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import (
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
from zheka.core.ids import ChargeId, FlatId, HouseId

router = APIRouter(tags=["Начисления"], route_class=DishkaRoute)


@router.get("/houses/{house_id}/tariffs", summary="Тарифы дома")
async def list_house_tariffs(
    house_id: HouseId,
    residency: ResidencyForHouseDep,
) -> list[TariffItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/flats/{flat_id}/charges", summary="Начисления квартиры")
async def list_flat_charges(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    limit: Limit = 12,
    offset: Offset = 0,
) -> Page[ChargeListItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/charges/{charge_id}", summary="Квитанция за период")
async def get_charge(
    charge_id: ChargeId,
    current_account: RequireConsentDep,
) -> ChargeCard:
    raise NotImplementedError("ещё не реализовано")


@router.get("/charges/{charge_id}/breakdown", summary="Разбор начисления")
async def get_charge_breakdown(
    charge_id: ChargeId,
    current_account: RequireConsentDep,
) -> ChargeBreakdown:
    raise NotImplementedError("ещё не реализовано")


@router.post("/charges/{charge_id}/dispute", summary="Оспорить начисление")
async def dispute_charge(
    charge_id: ChargeId,
    current_account: RequireConsentDep,
    body: DisputeChargeRequest,
) -> DisputeChargeResponse:
    raise NotImplementedError("ещё не реализовано")


@router.post("/charges/{charge_id}/pay", summary="Демо-оплата квитанции")
async def pay_charge_demo(
    charge_id: ChargeId,
    current_account: RequireConsentDep,
) -> PayChargeResponse:
    raise NotImplementedError("ещё не реализовано")
