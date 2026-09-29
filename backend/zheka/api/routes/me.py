from datetime import UTC, datetime
from http import HTTPStatus

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentAccountDep, CurrentUserDep, RequireConsentDep
from zheka.api.schemas.base import OkResponse
from zheka.api.schemas.me import (
    ConsentRequest,
    MeResponse,
    NotificationSettingsResponse,
    TrackEventRequest,
    UpdateAppearanceRequest,
    UpdateNotificationSettingsRequest,
    VerifyPhoneRequest,
)
from zheka.config import Config
from zheka.core.contact import verify_bridge_contact
from zheka.core.enums import EventSource
from zheka.core.services.events import EventsService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.profile import ProfileService

router = APIRouter(tags=["Профиль"], route_class=DishkaRoute)


@router.get("/me", summary="Профиль: дома, квартиры и организации")
async def get_me(
    current_account: CurrentAccountDep,
    profile_service: FromDishka[ProfileService],
) -> MeResponse:
    return MeResponse.of(await profile_service.me(current_account.user_id))


@router.post("/me/consent", summary="Согласие на обработку персональных данных")
async def accept_consent(
    current_account: CurrentAccountDep,
    profile_service: FromDishka[ProfileService],
    body: ConsentRequest,
) -> MeResponse:
    view = await profile_service.accept_consent(
        current_account.user_id,
        body.version,
        EventSource.MINIAPP,
    )
    return MeResponse.of(view)


@router.post(
    "/me/phone",
    summary="Подтвердить номер телефона из MAX",
    description=(
        "Тело - ответ WebApp.requestContact(). Подпись HMAC-SHA256 токеном бота "
        "над authDate, phone без «+» и userId, не старше суток. Номер видят "
        "только сотрудники УК домов жителя"
    ),
)
async def verify_phone(
    current_account: RequireConsentDep,
    current_user: CurrentUserDep,
    body: VerifyPhoneRequest,
    config: FromDishka[Config],
    profile_service: FromDishka[ProfileService],
) -> MeResponse:
    phone = verify_bridge_contact(
        body.phone,
        body.auth_date,
        body.hash,
        current_user.user.id,
        config.max.token,
        datetime.now(UTC),
    )
    return MeResponse.of(
        await profile_service.set_phone(current_account.user_id, phone),
    )


@router.delete("/me/phone", summary="Удалить номер телефона")
async def forget_phone(
    current_account: RequireConsentDep,
    profile_service: FromDishka[ProfileService],
) -> MeResponse:
    return MeResponse.of(await profile_service.set_phone(current_account.user_id, None))


@router.get("/me/notifications", summary="Настройки уведомлений")
async def get_notification_settings(
    current_account: RequireConsentDep,
    notifications_service: FromDishka[NotificationsService],
) -> NotificationSettingsResponse:
    levels = await notifications_service.levels(current_account.user_id)
    return NotificationSettingsResponse.of(levels)


@router.put("/me/notifications", summary="Изменить настройки уведомлений")
async def update_notification_settings(
    current_account: RequireConsentDep,
    body: UpdateNotificationSettingsRequest,
    notifications_service: FromDishka[NotificationsService],
) -> NotificationSettingsResponse:
    levels = await notifications_service.update(
        current_account.user_id,
        {item.category: item.level for item in body.settings},
    )
    return NotificationSettingsResponse.of(levels)


@router.post("/events", summary="Записать событие мини-аппа")
async def track_event(
    current_account: RequireConsentDep,
    events_service: FromDishka[EventsService],
    body: TrackEventRequest,
) -> OkResponse:
    await events_service.record(
        body.type,
        user_id=current_account.user_id,
        source=None if body.source is None else body.source.value,
        tab=body.tab,
        announcement_id=body.announcement_id,
    )
    return OkResponse()


@router.delete(
    "/me",
    summary="Удалить мои данные",
    status_code=HTTPStatus.NO_CONTENT,
)
async def forget_me(
    current_account: CurrentAccountDep,
    profile_service: FromDishka[ProfileService],
) -> None:
    await profile_service.forget(current_account.user_id)


@router.put("/me/appearance", summary="Изменить размер текста в мини-приложении")
async def update_appearance(
    current_account: RequireConsentDep,
    body: UpdateAppearanceRequest,
    profile_service: FromDishka[ProfileService],
) -> MeResponse:
    return MeResponse.of(
        await profile_service.set_text_size(current_account.user_id, body.text_size),
    )
