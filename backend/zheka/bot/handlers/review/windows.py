from datetime import timedelta

from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import MessageInput, TextInput
from maxo.dialogs.widgets.kbd import Button, Group, Row, Select, SwitchTo, WebApp
from maxo.dialogs.widgets.media import DynamicMedia
from maxo.dialogs.widgets.text import Const, Format, Multi
from maxo.enums import AttachmentType

from zheka.bot.cards import BACK, CANCEL
from zheka.bot.handlers.review.handlers import (
    get_ratings,
    get_rejection,
    get_review,
    on_accept,
    on_rating,
    on_reject,
    on_rejection,
    on_rejection_attachment,
    on_rejection_photo,
    on_send_rejection,
    on_start,
)
from zheka.bot.states import Review
from zheka.core.services.requests import AUTO_CLOSE_AFTER
from zheka.core.texts import OPEN_REQUEST

CARD_TEXT = "📋 Заявка №{request_id}: {status_label}\n\n{description}"
ASK_TEXT = (
    "🔍 Исполнитель закончил работу. Проверьте и примите ее\n"
    "⏳ Без ответа заявка закроется сама через "
    f"{AUTO_CLOSE_AFTER // timedelta(hours=1)} ч"
)
REJECTED_TEXT = "↩️ Повторная заявка ушла в УК"
RATED_TEXT = "⭐ Ваша оценка: {rating}"
RATING_TEXT = "⭐ Оцените работу"
REJECTION_TEXT = "📝 Расскажите, что сделано плохо"
REJECTION_PHOTO_TEXT = "📷 Пришлите фото того, что не так: так УК увидит проблему"
OPTIONAL_PHOTO_TEXT = "📷 Пришлите фото, если есть, или сразу отправьте"
PHOTOS_TEXT = "📎 Фото: {photos}"
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
        WebApp(
            Const(OPEN_REQUEST),
            Format("{bot_username}"),
            payload=Format("{request_payload}"),
            when=F["bot_username"],
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
        Multi(
            Const(REJECTION_TEXT),
            Format(PHOTOS_TEXT, when=F["photos"]),
            sep="\n\n",
        ),
        MessageInput(on_rejection_attachment, content_types=[AttachmentType.IMAGE]),
        TextInput(id="comment", on_success=on_rejection),
        CANCEL,
        state=Review.rejection,
        getter=get_rejection,
    ),
    Window(
        Multi(
            Const(REJECTION_PHOTO_TEXT, when=F["needs_photo"]),
            Const(OPTIONAL_PHOTO_TEXT, when=~F["needs_photo"]),
            Format(PHOTOS_TEXT, when=F["photos"]),
            sep="\n\n",
        ),
        MessageInput(on_rejection_photo, content_types=[AttachmentType.IMAGE]),
        Button(
            Const("📨 Отправить"),
            id="send_rejection",
            on_click=on_send_rejection,
            when=F["can_send"],
        ),
        Row(SwitchTo(BACK, id="to_rejection", state=Review.rejection), CANCEL),
        state=Review.rejection_photo,
        getter=get_rejection,
    ),
    on_start=on_start,
)
