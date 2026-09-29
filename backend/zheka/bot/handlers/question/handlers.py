from typing import Any

from dishka import FromDishka
from maxo import Bot
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import ManagedTextInput
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback, MessageCreated

from zheka.bot.cards import (
    app_payload,
    ask_in_default_stack,
    back_to_menu,
    web_app_name,
)
from zheka.bot.dialog_data import QuestionData
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import Question
from zheka.core.deeplinks import request_app_path
from zheka.core.enums import RequestActorRole, RequestChannel, RequestStatus
from zheka.core.errors import ZhekaError
from zheka.core.ids import RequestId
from zheka.core.services.requests import RequestsService
from zheka.core.texts import OPEN_REQUEST, question_card

ANSWER_SENT = "✅ Ответ передан в УК"


def _request_id(dialog_manager: DialogManager) -> RequestId:
    return RequestId(QuestionData.load_start(dialog_manager).request_id)


@inject
async def get_question(
    bot: Bot,
    dialog_manager: DialogManager,
    requests_service: FromDishka[RequestsService],
    **_: Any,
) -> dict[str, Any]:
    request_id = _request_id(dialog_manager)
    card = await requests_service.get_card(dialog_user_id(dialog_manager), request_id)
    question = next(
        (
            view.message.text
            for view in reversed(card.messages)
            if view.message.author_role == RequestActorRole.STAFF
        ),
        "",
    )
    return {
        "text": question_card(request_id, card.request.category, question),
        "can_answer": card.request.status is not RequestStatus.DONE,
        "bot_username": web_app_name(bot),
        "request_payload": app_payload(request_app_path(request_id)),
    }


async def on_answer_tap(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
) -> None:
    await ask_in_default_stack(
        dialog_manager,
        Question.answer,
        QuestionData(request_id=_request_id(dialog_manager)).to_data(),
    )


@inject
async def on_answer(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    text: str,
    requests_service: FromDishka[RequestsService],
) -> None:
    request_id = _request_id(dialog_manager)
    try:
        await requests_service.write(
            dialog_user_id(dialog_manager),
            request_id,
            text,
            RequestChannel.BOT,
        )
    except ZhekaError as error:
        await back_to_menu(dialog_manager, str(error))
        return
    await back_to_menu(
        dialog_manager,
        ANSWER_SENT,
        OPEN_REQUEST,
        request_app_path(request_id),
    )
