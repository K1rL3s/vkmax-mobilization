from html import escape
from typing import Any

from dishka import FromDishka
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import ManagedTextInput
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback, MessageCreated

from zheka.bot.cards import ask_in_default_stack, back_to_menu, photo_media, refused
from zheka.bot.dialog_data import ReviewData
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import Review
from zheka.core.enums import RequestChannel, RequestCompletionReason
from zheka.core.errors import ZhekaError
from zheka.core.ids import RequestId
from zheka.core.services.files import FilesService
from zheka.core.services.requests import (
    MAX_PHOTOS,
    MAX_RATING,
    MIN_RATING,
    RequestsService,
)
from zheka.core.texts import REQUEST_STATUS_LABELS

PHOTOS_PER_SIDE = MAX_PHOTOS // 2


def _request_id(dialog_manager: DialogManager) -> RequestId:
    return RequestId(ReviewData.load_start(dialog_manager).request_id)


@inject
async def get_review(
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
                *card.issue_photos[:PHOTOS_PER_SIDE],
                *card.result_photos[:PHOTOS_PER_SIDE],
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


@inject
async def on_rejection(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    comment: str,
    requests_service: FromDishka[RequestsService],
) -> None:
    try:
        card = await requests_service.reject(
            dialog_user_id(dialog_manager),
            _request_id(dialog_manager),
            comment,
            RequestChannel.BOT,
        )
    except ZhekaError as error:
        await back_to_menu(dialog_manager, str(error))
        return
    await back_to_menu(dialog_manager, repeat_sent(card.request.id))


def repeat_sent(request_id: RequestId) -> str:
    return f"↩️ Повторная заявка №{request_id} ушла в УК"
