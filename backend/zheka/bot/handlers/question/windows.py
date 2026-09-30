from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import TextInput
from maxo.dialogs.widgets.kbd import Button, WebApp
from maxo.dialogs.widgets.text import Const, Format

from zheka.bot.cards import CANCEL
from zheka.bot.handlers.question.handlers import get_question, on_answer, on_answer_tap
from zheka.bot.states import Question
from zheka.core.texts import OPEN_REQUEST

ANSWER_TEXT = "📝 Напишите ответ для УК"
ANSWER = "📝 Ответить"

question_dialog = Dialog(
    Window(
        Format("{text}"),
        Button(
            Const(ANSWER),
            id="answer",
            on_click=on_answer_tap,
            when=F["can_answer"],
        ),
        WebApp(
            Const(OPEN_REQUEST),
            Format("{bot_username}"),
            payload=Format("{request_payload}"),
            when=F["bot_username"],
        ),
        state=Question.card,
        getter=get_question,
    ),
    Window(
        Const(ANSWER_TEXT),
        TextInput(id="answer_text", on_success=on_answer),
        CANCEL,
        state=Question.answer,
    ),
)
