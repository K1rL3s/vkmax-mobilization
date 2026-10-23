from html import escape
from typing import Any

from dishka import FromDishka
from maxo import Bot
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback

from zheka.base import ZhekaType
from zheka.bot.cards import app_payload, web_app_name
from zheka.bot.dialog_data import VisitWindowsData
from zheka.bot.middlewares.user import dialog_user_id
from zheka.core import texts
from zheka.core.deeplinks import request_app_path
from zheka.core.enums import RequestChannel
from zheka.core.errors import ZhekaError
from zheka.core.ids import AccessRequestId, AccessSlotId, RequestId
from zheka.core.services.requests import RequestsService
from zheka.core.services.visits import VisitService, stale_visit

PICKED = "✅ {span} - выбрано"
OFFERED = "🕐 {span}"


class WindowItem(ZhekaType):
    id: int
    label: str


def _ids(dialog_manager: DialogManager) -> tuple[RequestId, AccessRequestId]:
    data = VisitWindowsData.load(dialog_manager)
    return RequestId(data.request_id), AccessRequestId(data.visit_id)


async def on_start(_start_data: Any, dialog_manager: DialogManager) -> None:
    VisitWindowsData.load_start(dialog_manager).dump(dialog_manager)


@inject
async def get_windows(
    bot: Bot,
    dialog_manager: DialogManager,
    requests_service: FromDishka[RequestsService],
    **_: Any,
) -> dict[str, Any]:
    request_id, visit_id = _ids(dialog_manager)
    notice = VisitWindowsData.load(dialog_manager).notice
    common = {
        "notice": None if notice is None else escape(notice),
        "bot_username": web_app_name(bot),
        "request_payload": app_payload(request_app_path(request_id)),
    }
    try:
        card = await requests_service.get_card(
            dialog_user_id(dialog_manager),
            request_id,
        )
    except ZhekaError as error:
        return {**common, "offer": escape(str(error)), "windows": [], "open": False}

    visit = card.visit
    gone = stale_visit(card.request, visit, visit_id)
    if visit is None or gone is not None:
        return {**common, "offer": f"🤷 {gone}", "windows": [], "open": False}
    house = card.house
    return {
        **common,
        "offer": texts.visit_offer(card.request, visit.visit.date),
        "windows": [
            WindowItem(
                id=window.id,
                label=(PICKED if window.id == visit.slot_id else OFFERED).format(
                    span=texts.visit_span(
                        house.local(window.starts_at),
                        window.minutes,
                    ),
                ),
            )
            for window in visit.windows
        ],
        "open": True,
    }


@inject
async def on_window(
    _callback: MessageCallback,
    _select: Any,
    dialog_manager: DialogManager,
    slot_id: int,
    visit_service: FromDishka[VisitService],
) -> None:
    request_id, _ = _ids(dialog_manager)
    notice = None
    try:
        await visit_service.pick(
            dialog_user_id(dialog_manager),
            request_id,
            AccessSlotId(slot_id),
        )
    except ZhekaError as error:
        notice = str(error)
    with VisitWindowsData.proxy(dialog_manager) as data:
        data.notice = notice


@inject
async def on_none_fits(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    visit_service: FromDishka[VisitService],
) -> None:
    request_id, visit_id = _ids(dialog_manager)
    notice = texts.VISIT_DECLINED
    try:
        await visit_service.decline(
            dialog_user_id(dialog_manager),
            request_id,
            visit_id,
            RequestChannel.BOT,
        )
    except ZhekaError as error:
        notice = str(error)
    with VisitWindowsData.proxy(dialog_manager) as data:
        data.notice = notice
