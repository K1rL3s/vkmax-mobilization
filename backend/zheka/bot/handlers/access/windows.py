from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.kbd import Column, Select
from maxo.dialogs.widgets.text import Const, Format, Multi

from zheka.bot.handlers.access.handlers import get_slots, on_slot, on_start
from zheka.bot.states import AccessSlots

SLOTS_TEXT = (
    "УК просит доступ в квартиру {date}\n{address}\n\n{reason}\n\n"
    "Выберите удобное время"
)
GONE_TEXT = "Этот запрос доступа вам больше не адресован"

access_dialog = Dialog(
    Window(
        Multi(
            Format(SLOTS_TEXT, when=F["available"]),
            Const(GONE_TEXT, when=~F["available"]),
            Format("{notice}", when=F["notice"]),
            sep="\n\n",
        ),
        Column(
            Select(
                Format("{item.label}"),
                id="slot",
                item_id_getter=lambda slot: slot.id,
                type_factory=int,
                items="slots",
                on_click=on_slot,
            )
        ),
        state=AccessSlots.pick,
        getter=get_slots,
    ),
    on_start=on_start,
)
