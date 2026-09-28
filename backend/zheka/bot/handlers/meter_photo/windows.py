from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import MessageInput, TextInput
from maxo.dialogs.widgets.kbd import Button, Column, Select, SwitchTo
from maxo.dialogs.widgets.text import Const, Format, Multi
from maxo.enums import AttachmentType

from zheka.bot.cards import TO_MENU
from zheka.bot.handlers.meter_photo.handlers import (
    get_confirm,
    get_meters,
    on_bad_value,
    on_meter,
    on_new_photo,
    on_send,
    on_start,
    on_value,
    volume_factory,
)
from zheka.bot.states import MeterPhoto

METER_TEXT = "📟 Какой это счетчик?"
PHOTO_TEXT = "📷 Пришлите фото счетчика одним сообщением"
WAIT_TEXT = "⏳ Распознаю показание"
UNREADABLE_TEXT = (
    "📷 Не разобрал цифры: переснимите без блика или напишите показание числом"
)
UNSAVED_TEXT = "📷 Фото не сохранилось, пришлите его еще раз"
EDIT_TEXT = "✏️ Напишите показание числом, например 123,456"

meter_photo_dialog = Dialog(
    Window(
        Const(METER_TEXT),
        Column(
            Select(
                Format("{item[label]}"),
                id="meter",
                item_id_getter=lambda meter: meter["id"],
                items="meters",
                on_click=on_meter,
            ),
        ),
        TO_MENU,
        state=MeterPhoto.meter,
        getter=get_meters,
    ),
    Window(
        Const(PHOTO_TEXT),
        MessageInput(on_new_photo, content_types=[AttachmentType.IMAGE]),
        TO_MENU,
        state=MeterPhoto.photo,
    ),
    Window(
        Const(WAIT_TEXT),
        TO_MENU,
        state=MeterPhoto.wait,
    ),
    Window(
        Multi(
            Format("{label} · {period}", when=F["label"]),
            Format("{line}", when=F["line"]),
            Const(UNREADABLE_TEXT, when=F["unreadable"]),
            Const(UNSAVED_TEXT, when=F["unsaved"]),
            Format("{notice}", when=F["notice"]),
            sep="\n",
        ),
        MessageInput(on_new_photo, content_types=[AttachmentType.IMAGE]),
        Button(
            Const("✅ Всё верно, отправить"),
            id="send_ack",
            on_click=on_send,
            when=F["can_send"] & F["ack"],
        ),
        Button(
            Const("✅ Отправить"),
            id="send",
            on_click=on_send,
            when=F["can_send"] & ~F["ack"],
        ),
        SwitchTo(Const("✏️ Исправить"), id="edit", state=MeterPhoto.edit),
        SwitchTo(Const("📷 Переснять"), id="rephoto", state=MeterPhoto.photo),
        TO_MENU,
        state=MeterPhoto.confirm,
        getter=get_confirm,
    ),
    Window(
        Const(EDIT_TEXT),
        TextInput(
            id="value",
            type_factory=volume_factory,
            on_success=on_value,
            on_error=on_bad_value,
        ),
        SwitchTo(Const("⬅️ Назад"), id="edit_back", state=MeterPhoto.confirm),
        TO_MENU,
        state=MeterPhoto.edit,
    ),
    on_start=on_start,
)
