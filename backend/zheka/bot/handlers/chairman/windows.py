from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.kbd import Button
from maxo.dialogs.widgets.text import Const, Format

from zheka.bot.handlers.chairman.handlers import (
    get_offer,
    on_accept,
    on_decline,
    on_start,
)
from zheka.bot.states import Chairman

chairman_dialog = Dialog(
    Window(
        Format("{offer}"),
        Button(Const("✅ Принять"), id="accept", on_click=on_accept),
        Button(Const("❌ Отказаться"), id="decline", on_click=on_decline),
        state=Chairman.accept,
        getter=get_offer,
    ),
    on_start=on_start,
)
