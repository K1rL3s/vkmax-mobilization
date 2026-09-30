from datetime import date
from typing import Any

from dishka import FromDishka
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import ManagedTextInput, MessageInput
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback, MessageCreated

from zheka.bot.cards import back_to_menu
from zheka.bot.dialog_data import MeterPhotoData, NewRequestData
from zheka.bot.handlers.fallback import on_free_text
from zheka.bot.meter_photo import publish_recognition, start_meter_photo
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import MeterPhoto
from zheka.broker.publisher import TaskPublisher
from zheka.core.enums import TariffZone
from zheka.core.errors import ZhekaError
from zheka.core.ids import MeterId
from zheka.core.services.meter_photo import (
    METER_UNIT,
    MeterPhotoService,
    anomaly,
    baseline,
    format_volume,
    meter_label,
    parse_volume,
)
from zheka.core.services.readings import SubmitResult

MONTHS = (
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
)
ANOMALY_TEXT = {
    "below": "❗ Показание меньше прошлого. Проверьте число и нажмите еще раз",
    "high": "❗ Расход намного больше обычного. Проверьте число и нажмите еще раз",
}
KOPECKS = 100


@inject
async def on_meter_photo(
    update: MessageCreated,
    widget: MessageInput,
    dialog_manager: DialogManager,
    service: FromDishka[MeterPhotoService],
    publisher: FromDishka[TaskPublisher],
) -> None:
    body = update.message.body
    photo_url = MeterPhotoData.photo_of(body)
    if NewRequestData.from_free_text(body) is not None or photo_url is None:
        await on_free_text(update, widget, dialog_manager)
        return
    await start_meter_photo(photo_url, dialog_manager, service, publisher)


async def on_start(_start_data: Any, dialog_manager: DialogManager) -> None:
    MeterPhotoData.load_start(dialog_manager).dump(dialog_manager)


@inject
async def get_meters(
    dialog_manager: DialogManager,
    service: FromDishka[MeterPhotoService],
    **_: Any,
) -> dict[str, Any]:
    choice = await service.meters(dialog_user_id(dialog_manager))
    return {
        "meters": [
            {"id": str(card.meter.id), "label": meter_label(card)}
            for card in choice.cards
        ],
    }


@inject
async def on_meter(
    _callback: MessageCallback,
    _select: Any,
    dialog_manager: DialogManager,
    meter_id: str,
    publisher: FromDishka[TaskPublisher],
) -> None:
    with MeterPhotoData.proxy(dialog_manager) as data:
        data.meter_id = int(meter_id) if meter_id.isdecimal() else None
    await dialog_manager.switch_to(MeterPhoto.wait)
    publish_recognition(
        publisher,
        dialog_manager,
        MeterPhotoData.load(dialog_manager),
    )


@inject
async def on_new_photo(
    update: MessageCreated,
    _widget: MessageInput,
    dialog_manager: DialogManager,
    publisher: FromDishka[TaskPublisher],
) -> None:
    with MeterPhotoData.proxy(dialog_manager) as data:
        data.photo_url = MeterPhotoData.photo_of(update.message.body)
        data.photo_name = None
        data.value = None
        data.recognized = None
        data.anomaly_ack = False
        data.notice = None
    await dialog_manager.switch_to(MeterPhoto.wait)
    publish_recognition(
        publisher,
        dialog_manager,
        MeterPhotoData.load(dialog_manager),
    )


@inject
async def get_confirm(
    dialog_manager: DialogManager,
    service: FromDishka[MeterPhotoService],
    **_: Any,
) -> dict[str, Any]:
    data = MeterPhotoData.load(dialog_manager)
    if data.meter_id is None or data.period is None:
        return {"label": None, "notice": data.notice}
    try:
        card = await service.card(
            dialog_user_id(dialog_manager),
            MeterId(data.meter_id),
        )
    except ZhekaError as error:
        return {"label": None, "notice": str(error)}
    period = date.fromisoformat(data.period)
    unit = METER_UNIT[card.meter.type]
    _since, previous = baseline(card, period)
    value = data.value
    line = None
    if value is not None:
        line = f"{format_volume(value)} {unit}"
        if previous is not None:
            line += (
                f", прошлое {format_volume(previous)}, "
                f"расход {format_volume(value - previous)} {unit}"
            )
    unread = value is None and data.photo_name is not None
    return {
        "label": meter_label(card),
        "period": f"{MONTHS[period.month - 1]} {period.year}",
        "line": line,
        "unreadable": unread and not data.manual,
        "manual": unread and data.manual,
        "unsaved": data.photo_name is None,
        "can_send": value is not None and data.photo_name is not None,
        "ack": data.anomaly_ack,
        "notice": data.notice,
    }


@inject
async def on_send(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    service: FromDishka[MeterPhotoService],
) -> None:
    data = MeterPhotoData.load(dialog_manager)
    if (
        data.value is None
        or data.photo_name is None
        or data.meter_id is None
        or data.period is None
    ):
        return
    user_id = dialog_user_id(dialog_manager)
    period = date.fromisoformat(data.period)
    try:
        card = await service.card(user_id, MeterId(data.meter_id))
        kind = anomaly(card, period, data.value)
        if kind is not None and not data.anomaly_ack:
            data.anomaly_ack = True
            data.notice = ANOMALY_TEXT[kind]
            data.dump(dialog_manager)
            return
        result = await service.submit(
            user_id,
            MeterId(data.meter_id),
            period,
            data.value,
            data.photo_name,
            data.recognized,
        )
    except ZhekaError as error:
        data.notice = f"😔 {error}"
        data.dump(dialog_manager)
        return
    await back_to_menu(
        dialog_manager,
        submitted_text(result, METER_UNIT[card.meter.type]),
    )


def submitted_text(result: SubmitResult, unit: str) -> str:
    used = result.row.consumption.get(TariffZone.SINGLE, 0)
    text = f"✅ Показание передано: расход {format_volume(used)} {unit}"
    amount = result.row.amount
    if amount is not None:
        text += f", около {(amount + KOPECKS // 2) // KOPECKS} ₽"
    return text


def volume_factory(text: str) -> int:
    value = parse_volume(text)
    if value is None:
        raise ValueError(text)
    return value


async def on_value(
    _update: MessageCreated,
    _widget: ManagedTextInput[int],
    dialog_manager: DialogManager,
    value: int,
) -> None:
    with MeterPhotoData.proxy(dialog_manager) as data:
        data.value = value
        data.anomaly_ack = False
        data.notice = None
    await dialog_manager.switch_to(MeterPhoto.confirm)


async def on_bad_value(
    _update: MessageCreated,
    _widget: ManagedTextInput[int],
    dialog_manager: DialogManager,
    _error: ValueError,
) -> None:
    with MeterPhotoData.proxy(dialog_manager) as data:
        data.notice = BAD_VALUE


BAD_VALUE = "📝 Не понял число. Напишите показание, например 123,456"
