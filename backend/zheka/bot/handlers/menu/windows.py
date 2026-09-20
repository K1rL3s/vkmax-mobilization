from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.kbd import WebApp
from maxo.dialogs.widgets.text import Const, Format

from zheka.bot.handlers.menu.handlers import get_menu
from zheka.bot.states import Menu

MENU_TEXT = (
    "Жэка Коммуналкин на связи.\n\n"
    "Подаю заявки в УК, показываю начисления и собираю показания счётчиков. "
    "Открывай приложение, чтобы найти свой дом."
)

menu_dialog = Dialog(
    Window(
        Const(MENU_TEXT),
        WebApp(
            Const("Открыть приложение"),
            Format("{bot_username}"),
            when=F["bot_username"],
        ),
        state=Menu.main,
        getter=get_menu,
    ),
)
