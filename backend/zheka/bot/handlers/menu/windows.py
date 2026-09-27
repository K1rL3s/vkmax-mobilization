from html import escape
from typing import Any

from dishka import FromDishka
from magic_filter import F
from maxo import Bot
from maxo.dialogs import Dialog, DialogManager, Window
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.kbd import Start, WebApp
from maxo.dialogs.widgets.text import Const, Format, Multi

from zheka.bot.cards import web_app_name
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import Menu, NewRequest, Onboarding
from zheka.core.services.profile import ProfileService

GREETING = "👋 Жэка Коммуналкин на связи"
MENU_TEXT = (
    f"{GREETING}\n\n"
    "Подаю заявки в УК, показываю начисления и собираю показания счетчиков. "
    "Начните с поиска своего дома - здесь или в приложении"
)
HOUSE_MENU_TEXT = (
    f"{GREETING}\n\n"
    "🏢 {address}\n"
    "Заявку можно подать здесь, показания, начисления и опросы - в приложении"
)
STAFF_TEXT = "🧑‍💼 Кабинет УК - в приложении"


@inject
async def get_menu(
    bot: Bot,
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    **_: Any,
) -> dict[str, Any]:
    me = await profile_service.me(dialog_user_id(dialog_manager))
    residency = me.latest_residency
    return {
        "bot_username": web_app_name(bot),
        "address": None if residency is None else escape(residency.house.address),
        "staff": me.is_staff,
    }


menu_dialog = Dialog(
    Window(
        Multi(
            Const(MENU_TEXT, when=~F["address"]),
            Format(HOUSE_MENU_TEXT, when=F["address"]),
            Const(STAFF_TEXT, when=F["staff"]),
            sep="\n\n",
        ),
        Start(
            Const("🔎 Найти дом"),
            id="find_house",
            state=Onboarding.method,
            when=~F["address"],
        ),
        Start(Const("📝 Подать заявку"), id="new_request", state=NewRequest.category),
        WebApp(
            Const("📱 Открыть приложение"),
            Format("{bot_username}"),
            when=F["bot_username"],
        ),
        Start(
            Const("🔎 Другой дом"),
            id="other_house",
            state=Onboarding.method,
            when=F["address"],
        ),
        state=Menu.main,
        getter=get_menu,
    ),
)
