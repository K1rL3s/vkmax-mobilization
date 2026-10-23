from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.kbd import Button, Column, Select, WebApp
from maxo.dialogs.widgets.text import Const, Format, Multi

from zheka.bot.handlers.visit.handlers import (
    get_windows,
    on_none_fits,
    on_start,
    on_window,
)
from zheka.bot.states import VisitWindows
from zheka.core.texts import OPEN_REQUEST

NONE_FITS = "🙅 Ни одно время не подходит"

visit_dialog = Dialog(
    Window(
        Multi(
            Format("{offer}"),
            Const("🕐 Выберите, когда вы будете дома", when=F["open"]),
            Format("{notice}", when=F["notice"]),
            sep="\n\n",
        ),
        Column(
            Select(
                Format("{item.label}"),
                id="window",
                item_id_getter=lambda window: window.id,
                type_factory=int,
                items="windows",
                on_click=on_window,
            ),
            Button(
                Const(NONE_FITS),
                id="none_fits",
                on_click=on_none_fits,
                when=F["open"],
            ),
        ),
        WebApp(
            Const(OPEN_REQUEST),
            Format("{bot_username}"),
            payload=Format("{request_payload}"),
            when=F["bot_username"],
        ),
        state=VisitWindows.pick,
        getter=get_windows,
    ),
    on_start=on_start,
)
