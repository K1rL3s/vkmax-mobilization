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

router = APIRouter(tags=["Профиль"], route_class=DishkaRoute)


@router.get("/me", summary="Профиль: дома, квартиры и организации")
async def get_me(current_account: CurrentAccountDep) -> MeResponse:
    raise NotImplementedError("ещё не реализовано")


@router.post("/me/consent", summary="Согласие на обработку персональных данных")
async def accept_consent(
    current_account: CurrentAccountDep,
    body: ConsentRequest,
) -> MeResponse:
    raise NotImplementedError("ещё не реализовано")


@router.get("/me/notifications", summary="Настройки уведомлений")
async def get_notification_settings(
    current_account: RequireConsentDep,
) -> NotificationSettingsResponse:
    raise NotImplementedError("ещё не реализовано")


@router.put("/me/notifications", summary="Изменить настройки уведомлений")
async def update_notification_settings(
    current_account: RequireConsentDep,
    body: UpdateNotificationSettingsRequest,
) -> NotificationSettingsResponse:
    raise NotImplementedError("ещё не реализовано")


@router.post("/events", summary="Записать событие мини-аппа")
async def track_event(
    current_account: RequireConsentDep,
    body: TrackEventRequest,
) -> OkResponse:
    raise NotImplementedError("ещё не реализовано")
