from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter
from maxo import Bot
from maxo.utils.deeplink import create_start_link

from zheka.api.dependencies import (
    RequireConsentDep,
    ResidencyForFlatDep,
    ResidencyForFlatHouseDep,
)
from zheka.api.schemas.base import OkResponse
from zheka.api.schemas.flats import (
    CreateFlatInviteRequest,
    FlatCard,
    FlatInviteItem,
    FlatResidentItem,
    FlatVerificationRequest,
    TenancyItem,
    VerificationRequestItem,
    VerifyFlatByQrRequest,
    VerifyFlatRequest,
    VerifyFlatResponse,
)
from zheka.api.schemas.houses import ResidencySummary
from zheka.core.deeplinks import flat_invite_payload
from zheka.core.errors import TooManyRequests
from zheka.core.ids import FlatId, ResidentId
from zheka.core.services.flats import FlatsService
from zheka.infra.quota import VerifyQuota

router = APIRouter(tags=["Квартиры"], route_class=DishkaRoute)


@router.get("/flats/{flat_id}", summary="Карточка квартиры")
async def get_flat_card(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    flats_service: FromDishka[FlatsService],
) -> FlatCard:
    return FlatCard.of(await flats_service.flat_card(residency.user_id, flat_id))


@router.post(
    "/flats/{flat_id}/verify",
    summary="Подтвердить квартиру лицевым счетом или QR квитанции",
)
async def verify_flat(
    flat_id: FlatId,
    residency: ResidencyForFlatHouseDep,
    flats_service: FromDishka[FlatsService],
    body: VerifyFlatRequest | VerifyFlatByQrRequest,
    quota: FromDishka[VerifyQuota],
) -> VerifyFlatResponse:
    if not quota.take(residency.user_id):
        raise TooManyRequests
    if isinstance(body, VerifyFlatByQrRequest):
        result = await flats_service.verify_by_qr(
            residency.user_id,
            flat_id,
            body.payment_qr,
        )
    else:
        result = await flats_service.verify(
            residency.user_id,
            flat_id,
            body.account_no,
        )
    return VerifyFlatResponse.model_validate(result)


@router.post(
    "/flats/{flat_id}/verification-request",
    summary="Запросить подтверждение квартиры у УК",
)
async def request_flat_verification(
    flat_id: FlatId,
    residency: ResidencyForFlatHouseDep,
    flats_service: FromDishka[FlatsService],
    body: FlatVerificationRequest,
) -> VerificationRequestItem:
    view = await flats_service.request_verification(
        residency.user_id,
        flat_id,
        body.account_no,
        body.comment,
    )
    return VerificationRequestItem.of(view)


@router.get("/flats/{flat_id}/residents", summary="Жители квартиры")
async def list_flat_residents(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    flats_service: FromDishka[FlatsService],
) -> list[FlatResidentItem]:
    views = await flats_service.list_residents(residency.user_id, flat_id)
    return [FlatResidentItem.of(view) for view in views]


@router.post("/flats/{flat_id}/invites", summary="Код приглашения в квартиру")
async def create_flat_invite(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    flats_service: FromDishka[FlatsService],
    bot: FromDishka[Bot],
    body: CreateFlatInviteRequest,
) -> FlatInviteItem:
    invite = await flats_service.create_invite(
        residency.user_id,
        flat_id,
        body.expires_in_hours,
        body.max_activations,
    )
    return FlatInviteItem.of(
        invite,
        create_start_link(bot, flat_invite_payload(invite.code)),
    )


@router.get("/flats/{flat_id}/invites", summary="Коды приглашения в квартиру")
async def list_flat_invites(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    flats_service: FromDishka[FlatsService],
    bot: FromDishka[Bot],
) -> list[FlatInviteItem]:
    invites = await flats_service.list_invites(residency.user_id, flat_id)
    return [
        FlatInviteItem.of(
            invite,
            create_start_link(bot, flat_invite_payload(invite.code)),
        )
        for invite in invites
    ]


@router.delete("/flat-invites/{code}", summary="Отозвать код приглашения")
async def revoke_flat_invite(
    code: str,
    current_account: RequireConsentDep,
    flats_service: FromDishka[FlatsService],
) -> OkResponse:
    await flats_service.revoke_invite(current_account.user_id, code)
    return OkResponse()


@router.post("/flat-invites/{code}/activate", summary="Активировать код квартиры")
async def activate_flat_invite(
    code: str,
    current_account: RequireConsentDep,
    flats_service: FromDishka[FlatsService],
) -> ResidencySummary:
    view = await flats_service.activate_invite(current_account.user_id, code)
    return ResidencySummary.of(view)


@router.delete(
    "/flats/{flat_id}/tenants/{resident_id}",
    summary="Завершить аренду",
    description=(
        "Собственник удаляет арендатора из квартиры и отзывает открытые коды "
        "приглашения, арендатору приходит сообщение в бот"
    ),
)
async def end_tenancy(
    flat_id: FlatId,
    resident_id: ResidentId,
    residency: ResidencyForFlatDep,
    flats_service: FromDishka[FlatsService],
) -> OkResponse:
    await flats_service.end_tenancy(residency.user_id, flat_id, resident_id)
    return OkResponse()


@router.get("/flats/{flat_id}/tenancies", summary="История аренды квартиры")
async def list_tenancies(
    flat_id: FlatId,
    residency: ResidencyForFlatDep,
    flats_service: FromDishka[FlatsService],
) -> list[TenancyItem]:
    views = await flats_service.tenancies(residency.user_id, flat_id)
    return [TenancyItem.of(view) for view in views]
