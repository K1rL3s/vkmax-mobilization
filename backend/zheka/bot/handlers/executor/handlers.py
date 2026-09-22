from html import escape
from typing import Any

from dishka import FromDishka
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import MessageInput
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback, MessageCreated, PhotoAttachment

from zheka.bot.cards import ask_in_default_stack, back_to_menu, photo_media, refused
from zheka.bot.dialog_data import ExecutorCardData
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import ExecutorCard
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import CATEGORY_RULES, RequestStatus
from zheka.core.errors import ZhekaError
from zheka.core.ids import RequestId
from zheka.core.services.admin_requests import AdminRequestsService
from zheka.core.services.files import FilesService
from zheka.core.services.requests import MAX_PHOTOS
from zheka.core.texts import REQUEST_STATUS_LABELS

PHOTO_TAKEN = "Фото получил, карточка заявки обновится"


def _request_id(dialog_manager: DialogManager) -> RequestId:
    return RequestId(ExecutorCardData.load_start(dialog_manager).request_id)


@inject
async def get_card(
    dialog_manager: DialogManager,
    admin_requests_service: FromDishka[AdminRequestsService],
    files_service: FromDishka[FilesService],
    **_: Any,
) -> dict[str, Any]:
    request_id = _request_id(dialog_manager)
    card = await admin_requests_service.executor_card(
        dialog_user_id(dialog_manager),
        request_id,
    )
    if card is None:
        return {"request_id": request_id, "mine": False, "status": None, "photos": []}

    request = card.request
    place = card.house.address
    if card.flat is not None:
        place = f"{place}, кв. {card.flat.number}"
    return {
        "request_id": request_id,
        "mine": True,
        "status": request.status,
        "status_label": REQUEST_STATUS_LABELS[request.status],
        "place": escape(place),
        "category": CATEGORY_RULES[request.category].label,
        "description": escape(request.description),
        "photos": photo_media(files_service, card.issue_photos[:MAX_PHOTOS]),
    }


@inject
async def on_advance(
    callback: MessageCallback,
    button: Button,
    dialog_manager: DialogManager,
    admin_requests_service: FromDishka[AdminRequestsService],
) -> None:
    try:
        await admin_requests_service.executor_advance(
            dialog_user_id(dialog_manager),
            _request_id(dialog_manager),
            RequestStatus(str(button.widget_id)),
            [],
        )
    except ZhekaError as error:
        await refused(callback, error)


async def on_ready(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
) -> None:
    await ask_in_default_stack(
        dialog_manager,
        ExecutorCard.result_photo,
        ExecutorCardData(request_id=_request_id(dialog_manager)).to_data(),
    )


@inject
async def on_result_photo(
    update: MessageCreated,
    _widget: MessageInput,
    dialog_manager: DialogManager,
    publisher: FromDishka[TaskPublisher],
) -> None:
    urls = [
        attach.payload.url
        for attach in update.message.body.attachments or []
        if isinstance(attach, PhotoAttachment)
    ]
    publisher.publish(
        TaskName.ATTACH_RESULT_PHOTO,
        user_id=dialog_user_id(dialog_manager),
        request_id=_request_id(dialog_manager),
        photo_urls=urls[:MAX_PHOTOS],
    )
    await back_to_menu(dialog_manager, PHOTO_TAKEN)
