from html import escape
from typing import Any

from dishka import FromDishka
from maxo import Bot
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import ManagedTextInput, MessageInput
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback, MessageCreated

from zheka.bot.cards import (
    app_payload,
    ask_in_default_stack,
    back_to_menu,
    photo_media,
    refused,
    web_app_name,
)
from zheka.bot.dialog_data import ReviewData
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import Review
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.deeplinks import request_app_path
from zheka.core.enums import CATEGORY_RULES, RequestCompletionReason
from zheka.core.errors import ZhekaError
from zheka.core.ids import RequestId
from zheka.core.services.files import FilesService
from zheka.core.services.requests import (
    MAX_ATTACHMENTS,
    MAX_RATING,
    MIN_RATING,
    RequestsService,
)
from zheka.core.texts import REQUEST_STATUS_LABELS

PHOTOS_PER_SIDE = MAX_ATTACHMENTS // 2
REJECTION_TAKEN = "⏳ Принял, оформляю повторную заявку"


def _request_id(dialog_manager: DialogManager) -> RequestId:
    return RequestId(ReviewData.load_start(dialog_manager).request_id)


@inject
async def get_review(
    bot: Bot,
    dialog_manager: DialogManager,
    requests_service: FromDishka[RequestsService],
    files_service: FromDishka[FilesService],
    **_: Any,
) -> dict[str, Any]:
    request_id = _request_id(dialog_manager)
    card = await requests_service.get_card(dialog_user_id(dialog_manager), request_id)
    request = card.request
    return {
        "request_id": request_id,
        "bot_username": web_app_name(bot),
        "request_payload": app_payload(request_app_path(request_id)),
        "status_label": REQUEST_STATUS_LABELS[request.status],
        "description": escape(request.description),
        "can_review": card.can_review,
        "can_rate": card.can_rate,
        "rating": request.rating,
        "rejected": request.completion_reason
        is RequestCompletionReason.RESIDENT_REJECTED,
        "photos": photo_media(
            files_service,
            [
                *card.issue_attachments[:PHOTOS_PER_SIDE],
                *card.result_attachments[:PHOTOS_PER_SIDE],
            ],
        ),
    }


async def get_ratings(**_: Any) -> dict[str, Any]:
    return {"ratings": list(range(MIN_RATING, MAX_RATING + 1))}


@inject
async def on_accept(
    callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    requests_service: FromDishka[RequestsService],
) -> None:
    try:
        await requests_service.accept(
            dialog_user_id(dialog_manager),
            _request_id(dialog_manager),
        )
    except ZhekaError as error:
        await refused(callback, error)
        return
    await dialog_manager.switch_to(Review.rating)


async def on_reject(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
) -> None:
    await ask_in_default_stack(
        dialog_manager,
        Review.rejection,
        ReviewData(request_id=_request_id(dialog_manager)).to_data(),
    )


@inject
async def on_rating(
    callback: MessageCallback,
    _select: Any,
    dialog_manager: DialogManager,
    rating: int,
    requests_service: FromDishka[RequestsService],
) -> None:
    try:
        await requests_service.rate(
            dialog_user_id(dialog_manager),
            _request_id(dialog_manager),
            rating,
            None,
        )
    except ZhekaError as error:
        await refused(callback, error)
    await dialog_manager.switch_to(Review.card)


async def on_rejection(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    comment: str,
) -> None:
    with ReviewData.proxy(dialog_manager) as data:
        data.comment = comment
    await dialog_manager.switch_to(Review.rejection_photo)


def repeat_sent(request_id: RequestId) -> str:
    return f"↩️ Повторная заявка №{request_id} ушла в УК"


async def on_start(_start_data: Any, dialog_manager: DialogManager) -> None:
    ReviewData.load_start(dialog_manager).dump(dialog_manager)


@inject
async def get_rejection(
    dialog_manager: DialogManager,
    requests_service: FromDishka[RequestsService],
    **_: Any,
) -> dict[str, Any]:
    data = ReviewData.load(dialog_manager)
    card = await requests_service.get_card(
        dialog_user_id(dialog_manager),
        RequestId(data.request_id),
    )
    needs_photo = CATEGORY_RULES[card.request.category].rejection_needs_photo
    return {
        "photos": len(data.photos),
        "needs_photo": needs_photo,
        "can_send": bool(data.photos) or not needs_photo,
    }


async def on_rejection_photo(
    update: MessageCreated,
    _widget: MessageInput,
    dialog_manager: DialogManager,
) -> None:
    with ReviewData.proxy(dialog_manager) as data:
        data.attach_photos(update.message.body)


async def on_rejection_attachment(
    update: MessageCreated,
    widget: MessageInput,
    dialog_manager: DialogManager,
) -> None:
    await on_rejection_photo(update, widget, dialog_manager)
    caption = (update.message.body.text or "").strip()
    if not caption:
        return
    with ReviewData.proxy(dialog_manager) as data:
        data.comment = caption
    await dialog_manager.switch_to(Review.rejection_photo)


@inject
async def on_send_rejection(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    publisher: FromDishka[TaskPublisher],
) -> None:
    data = ReviewData.load(dialog_manager)
    publisher.publish(
        TaskName.REJECT_BOT_REQUEST,
        user_id=dialog_user_id(dialog_manager),
        request_id=data.request_id,
        comment=data.comment,
        photo_urls=data.photos,
    )
    await back_to_menu(dialog_manager, REJECTION_TAKEN)
