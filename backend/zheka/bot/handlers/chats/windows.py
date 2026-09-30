from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import TextInput
from maxo.dialogs.widgets.kbd import Button, ScrollingGroup, Select
from maxo.dialogs.widgets.text import Const, Format, Multi

from zheka.bot.cards import CANCEL
from zheka.bot.handlers.chats.handlers import (
    BOUND_TEXT,
    get_binding,
    get_houses,
    on_code,
    on_house,
    on_rights,
    on_start,
)
from zheka.bot.states import ChatBinding

HOUSE_TEXT = "🏢 Вы добавили меня в чат «{title}». К какому дому привязать?"
CODE_TEXT = (
    "🔑 Привязать чат «{title}» к дому может УК или председатель. Если у вас "
    "есть код привязки, отправьте его сюда"
)
RIGHTS_TEXT = "🛡 Повысьте меня до администратора в чате «{title}» и нажмите «Готово»"
NOTICE = Format("{notice}", when=F["notice"])
HOUSES_PAGE = 20

chat_binding_dialog = Dialog(
    Window(
        Format(HOUSE_TEXT),
        ScrollingGroup(
            Select(
                Format("🏢 {item.title}"),
                id="house",
                item_id_getter=lambda house: house.id,
                type_factory=int,
                items="houses",
                on_click=on_house,
            ),
            id="houses_scroll",
            width=1,
            height=HOUSES_PAGE,
            hide_on_single_page=True,
        ),
        state=ChatBinding.house,
        getter=get_houses,
    ),
    Window(
        Multi(Format(CODE_TEXT), NOTICE, sep="\n\n"),
        TextInput(id="code", on_success=on_code),
        CANCEL,
        state=ChatBinding.code,
        getter=get_binding,
    ),
    Window(
        Multi(Format(RIGHTS_TEXT), NOTICE, sep="\n\n"),
        Button(Const("✅ Готово"), id="rights", on_click=on_rights),
        state=ChatBinding.rights,
        getter=get_binding,
    ),
    Window(Format(BOUND_TEXT), state=ChatBinding.done, getter=get_binding),
    on_start=on_start,
)
