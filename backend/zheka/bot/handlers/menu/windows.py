from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.kbd import Start, WebApp
from maxo.dialogs.widgets.text import Const, Format

from zheka.bot.handlers.menu.handlers import get_menu
from zheka.bot.states import Menu, NewRequest, Onboarding

MENU_TEXT = (
    "👋 Жэка Коммуналкин на связи\n\n"
    "Подаю заявки в УК, показываю начисления и собираю показания счетчиков. "
    "Начните с поиска своего дома - здесь или в приложении"
)

menu_dialog = Dialog(
    Window(
        Const(MENU_TEXT),
        Start(Const("🔎 Найти дом"), id="find_house", state=Onboarding.method),
        Start(Const("📝 Подать заявку"), id="new_request", state=NewRequest.category),
        WebApp(
            Const("📱 Открыть приложение"),
            Format("{bot_username}"),
            when=F["bot_username"],
        ),
        state=Menu.main,
        getter=get_menu,
    ),
)
