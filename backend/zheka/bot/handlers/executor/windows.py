from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import MessageInput
from maxo.dialogs.widgets.kbd import Button, Cancel
from maxo.dialogs.widgets.media import DynamicMedia
from maxo.dialogs.widgets.text import Const, Format, Multi
from maxo.enums import AttachmentType

from zheka.bot.handlers.executor.handlers import (
    get_card,
    on_advance,
    on_ready,
    on_result_photo,
)
from zheka.bot.states import ExecutorCard
from zheka.core.enums import RequestStatus

CARD_TEXT = "Заявка №{request_id}: {status_label}\n{place}\n{category}\n\n{description}"
HANDED_OVER_TEXT = "Заявку №{request_id} передали другому исполнителю"
RESULT_PHOTO_TEXT = "Пришлите фото результата"

executor_dialog = Dialog(
    Window(
        Multi(
            Format(CARD_TEXT, when=F["mine"]), Format(HANDED_OVER_TEXT, when=~F["mine"])
        ),
        DynamicMedia("photos"),
        Button(
            Const("Принял"),
            id=RequestStatus.ACCEPTED.value,
            on_click=on_advance,
            when=F["status"] == RequestStatus.NEW,
        ),
        Button(
            Const("Выехал"),
            id=RequestStatus.IN_PROGRESS.value,
            on_click=on_advance,
            when=F["status"] == RequestStatus.ACCEPTED,
        ),
        Button(
            Const("Готово"),
            id="ready",
            on_click=on_ready,
            when=F["status"] == RequestStatus.IN_PROGRESS,
        ),
        state=ExecutorCard.card,
        getter=get_card,
    ),
    Window(
        Const(RESULT_PHOTO_TEXT),
        MessageInput(on_result_photo, content_types=[AttachmentType.IMAGE]),
        Cancel(Const("Отмена")),
        state=ExecutorCard.result_photo,
    ),
)
