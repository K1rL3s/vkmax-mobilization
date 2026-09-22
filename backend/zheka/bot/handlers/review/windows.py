from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import TextInput
from maxo.dialogs.widgets.kbd import Button, Group, Select, SwitchTo
from maxo.dialogs.widgets.media import DynamicMedia
from maxo.dialogs.widgets.text import Const, Format, Multi

from zheka.bot.cards import CANCEL
from zheka.bot.handlers.review.handlers import (
    get_ratings,
    get_review,
    on_accept,
    on_rating,
    on_reject,
    on_rejection,
)
from zheka.bot.states import Review

CARD_TEXT = "📋 Заявка №{request_id}: {status_label}\n\n{description}"
ASK_TEXT = "🔍 Исполнитель закончил работу. Проверьте и примите ее"
REJECTED_TEXT = "↩️ Повторная заявка ушла в УК"
RATED_TEXT = "⭐ Ваша оценка: {rating}"
RATING_TEXT = "⭐ Оцените работу"
REJECTION_TEXT = "✍️ Расскажите, что сделано плохо"
KEYCAP = "️⃣"

review_dialog = Dialog(
    Window(
        Multi(
            Format(CARD_TEXT),
            Const(ASK_TEXT, when=F["can_review"]),
            Const(REJECTED_TEXT, when=F["rejected"]),
            Format(RATED_TEXT, when=F["rating"]),
            sep="\n\n",
        ),
        DynamicMedia("photos"),
        Button(
            Const("👍 Принять"),
            id="accept",
            on_click=on_accept,
            when=F["can_review"],
        ),
        Button(
            Const("👎 Сделано плохо"),
            id="reject",
            on_click=on_reject,
            when=F["can_review"],
        ),
        SwitchTo(
            Const("⭐ Оценить"),
            id="to_rating",
            state=Review.rating,
            when=F["can_rate"],
        ),
        state=Review.card,
        getter=get_review,
    ),
    Window(
        Const(RATING_TEXT),
        Group(
            Select(
                Format("{item}" + KEYCAP),
                id="rating",
                item_id_getter=str,
                items="ratings",
                type_factory=int,
                on_click=on_rating,
            ),
            width=5,
        ),
        SwitchTo(Const("⏰ Позже"), id="to_card", state=Review.card),
        state=Review.rating,
        getter=get_ratings,
    ),
    Window(
        Const(REJECTION_TEXT),
        TextInput(id="comment", on_success=on_rejection),
        CANCEL,
        state=Review.rejection,
    ),
)
