from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import RequireConsentDep, ResidencyForFlatDep
from zheka.api.schemas.base import OkResponse
from zheka.api.schemas.flats import (
    CreateFlatInviteRequest,
    FlatCard,
    FlatInviteItem,
    FlatResidentItem,
    FlatVerificationRequest,
    VerificationRequestItem,
    VerifyFlatRequest,
    VerifyFlatResponse,
)
from zheka.api.schemas.houses import ResidencySummary
from zheka.core.ids import FlatId

router = APIRouter(tags=["Квартиры"], route_class=DishkaRoute)


@router.get("/flats/{flat_id}", summary="Карточка квартиры")
async def get_flat_card(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
) -> FlatCard:
    raise NotImplementedError("ещё не реализовано")


@router.post("/flats/{flat_id}/verify", summary="Подтвердить квартиру лицевым счетом")
async def verify_flat(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    body: VerifyFlatRequest,
) -> VerifyFlatResponse:
    raise NotImplementedError("ещё не реализовано")


@router.post(
    "/flats/{flat_id}/verification-request",
    summary="Запросить подтверждение квартиры у УК",
)
async def request_flat_verification(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    body: FlatVerificationRequest,
) -> VerificationRequestItem:
    raise NotImplementedError("ещё не реализовано")


@router.get("/flats/{flat_id}/residents", summary="Жители квартиры")
async def list_flat_residents(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
) -> list[FlatResidentItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post("/flats/{flat_id}/invites", summary="Код приглашения в квартиру")
async def create_flat_invite(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    body: CreateFlatInviteRequest,
) -> FlatInviteItem:
    raise NotImplementedError("ещё не реализовано")


@router.get("/flats/{flat_id}/invites", summary="Коды приглашения в квартиру")
async def list_flat_invites(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
) -> list[FlatInviteItem]:
    raise NotImplementedError("ещё не реализовано")


@router.delete("/flat-invites/{code}", summary="Отозвать код приглашения")
async def revoke_flat_invite(
    code: str,
    current_account: RequireConsentDep,
) -> OkResponse:
    raise NotImplementedError("ещё не реализовано")


@router.post("/flat-invites/{code}/activate", summary="Активировать код квартиры")
async def activate_flat_invite(
    code: str,
    current_account: RequireConsentDep,
) -> ResidencySummary:
    raise NotImplementedError("ещё не реализовано")
