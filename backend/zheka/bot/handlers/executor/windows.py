from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import MessageInput, TextInput
from maxo.dialogs.widgets.kbd import Button
from maxo.dialogs.widgets.media import DynamicMedia
from maxo.dialogs.widgets.text import Const, Format, Multi
from maxo.enums import AttachmentType

from zheka.bot.cards import CANCEL
from zheka.bot.handlers.executor.handlers import (
    get_card,
    on_advance,
    on_decline,
    on_decline_reason,
    on_ready,
    on_result_photo,
)
from zheka.bot.states import ExecutorCard
from zheka.core.enums import RequestStatus
from zheka.infra.database.repos.requests import OPEN_STATUSES

CARD_TEXT = (
    "🛠 Заявка №{request_id}: {status_label}\n{place}\n{category}\n\n{description}"
)
NOT_YOURS_TEXT = "🔀 Заявка №{request_id} больше не у вас"
RESULT_PHOTO_TEXT = "📷 Пришлите фото результата"
DECLINE_TEXT = "📝 Почему не получится?"

executor_dialog = Dialog(
    Window(
        Multi(
            Format(CARD_TEXT, when=F["mine"]),
            Format("🎬 Видео: {videos}", when=F["mine"] & F["videos"]),
            Format(NOT_YOURS_TEXT, when=~F["mine"]),
        ),
        DynamicMedia("photos"),
        Button(
            Const("✅ Принял"),
            id=RequestStatus.ACCEPTED.value,
            on_click=on_advance,
            when=F["status"] == RequestStatus.NEW,
        ),
        Button(
            Const("🚗 Выехал"),
            id=RequestStatus.IN_PROGRESS.value,
            on_click=on_advance,
            when=F["status"] == RequestStatus.ACCEPTED,
        ),
        Button(
            Const("🏁 Готово"),
            id="ready",
            on_click=on_ready,
            when=F["status"] == RequestStatus.IN_PROGRESS,
        ),
        Button(
            Const("🙅 Не могу"),
            id="decline",
            on_click=on_decline,
            when=F["status"].in_(OPEN_STATUSES),
        ),
        state=ExecutorCard.card,
        getter=get_card,
    ),
    Window(
        Const(RESULT_PHOTO_TEXT),
        MessageInput(on_result_photo, content_types=[AttachmentType.IMAGE]),
        CANCEL,
        state=ExecutorCard.result_photo,
    ),
    Window(
        Const(DECLINE_TEXT),
        TextInput(id="reason", on_success=on_decline_reason),
        CANCEL,
        state=ExecutorCard.decline,
    ),
)
