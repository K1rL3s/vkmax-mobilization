from html import escape
from typing import Any

from dishka import FromDishka
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.types import MessageCallback

from zheka.base import ZhekaType
from zheka.bot.dialog_data import AccessSlotsData
from zheka.bot.middlewares.user import dialog_user_id
from zheka.core.errors import ZhekaError
from zheka.core.ids import AccessRequestId, AccessSlotId
from zheka.core.services.access import AccessService

PICKED = "{time} - выбрано"


class SlotItem(ZhekaType):
    id: int
    label: str


def _access_request_id(dialog_manager: DialogManager) -> AccessRequestId:
    return AccessRequestId(AccessSlotsData.load(dialog_manager).access_request_id)


async def on_start(_start_data: Any, dialog_manager: DialogManager) -> None:
    AccessSlotsData.load_start(dialog_manager).dump(dialog_manager)


@inject
async def get_slots(
    dialog_manager: DialogManager, access_service: FromDishka[AccessService], **_: Any
) -> dict[str, Any]:
    notice = AccessSlotsData.load(dialog_manager).notice
    try:
        view = await access_service.resident_view(
            dialog_user_id(dialog_manager), _access_request_id(dialog_manager)
        )
    except ZhekaError as error:
        # квартиру отвязали или заблокировали, пока окно висело: геттер,
        # который упал бы, отдал бы окно роутеру ошибок
        return {"available": False, "notice": escape(str(error)), "slots": []}

    request = view.request
    slots = [
        SlotItem(
            id=slot.slot.id,
            label=(
                PICKED.format(time=f"{slot.slot.starts_at:%H:%M}")
                if slot.slot.id == view.my_slot_id
                else f"{slot.slot.starts_at:%H:%M}"
            ),
        )
        for slot in view.slots
        if slot.slot.id == view.my_slot_id or slot.taken < slot.slot.capacity
    ]
    return {
        "available": True,
        "address": escape(view.address),
        "date": f"{request.date:%d.%m.%Y}",
        "reason": escape(request.reason),
        # отказ несет причину блокировки от УК, а бот пишет в HTML
        "notice": None if notice is None else escape(notice),
        "slots": slots,
    }


@inject
async def on_slot(
    _callback: MessageCallback,
    # Any по той же причине, что в онбординге: overload у inject не разбирает
    # четырехаргументный колбэк с Select
    _select: Any,
    dialog_manager: DialogManager,
    slot_id: int,
    access_service: FromDishka[AccessService],
) -> None:
    notice = None
    try:
        await access_service.pick(
            dialog_user_id(dialog_manager),
            _access_request_id(dialog_manager),
            AccessSlotId(slot_id),
        )
    except ZhekaError as error:
        # окно заняли, пока клавиатура висела: отказ ничего не записал, и
        # следующий ход жителя - другое окно, а не роутер ошибок
        notice = str(error)
    with AccessSlotsData.proxy(dialog_manager) as data:
        data.notice = notice
