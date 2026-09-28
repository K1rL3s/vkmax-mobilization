from http import HTTPStatus

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentAccountDep, RequireConsentDep
from zheka.api.schemas.base import OkResponse
from zheka.api.schemas.me import (
    ConsentRequest,
    MeResponse,
    NotificationSettingsResponse,
    TrackEventRequest,
    UpdateNotificationSettingsRequest,
)
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
