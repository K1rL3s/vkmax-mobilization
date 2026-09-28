from html import escape
from typing import Any

from dishka import FromDishka
from magic_filter import F
from maxo import Bot
from maxo.dialogs import Dialog, DialogManager, Window
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import MessageInput
from maxo.dialogs.widgets.kbd import CopyText, Start, SwitchTo, WebApp
from maxo.dialogs.widgets.text import Const, Format, Multi
from maxo.enums import AttachmentType

from zheka.bot.cards import EMERGENCY, TO_MENU, app_payload, web_app_name
from zheka.bot.handlers.fallback import on_free_text
from zheka.bot.handlers.meter_photo.handlers import on_meter_photo
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import Menu, NewRequest, Onboarding
from zheka.core.deeplinks import ADMIN_APP_PATH
from zheka.core.services.profile import ProfileService
from zheka.core.texts import CABINET_BUTTON

GREETING = "👋 Жэка Коммуналкин на связи"
MENU_TEXT = (
    f"{GREETING}\n\n"
    "Подаю заявки в УК, показываю начисления и собираю показания счетчиков. "
    "Начните с поиска своего дома - здесь или в приложении"
)
HOUSE_MENU_TEXT = (
    f"{GREETING}\n\n"
    "🏢 {address}\n"
    "Заявку можно подать здесь, показания, начисления и опросы - в приложении\n"
    "✍️ Можно просто написать, что случилось, - я оформлю заявку"
)
STAFF_TEXT = "🧑‍💼 Кабинет УК - в приложении"
EMERGENCY_TEXT = (
    "🚨 Угроза жизни, пожар или дым - звоните 112\n\n"
    "🔥 Пахнет газом - не включайте свет и приборы, не зажигайте огонь, "
    "откройте окна, выйдите и звоните 104 или 112\n\n"
    "💧 Течет вода - перекройте кран на стояке или под раковиной, "
    "не трогайте приборы мокрыми руками\n\n"
    "⚡ Искрит проводка или пахнет гарью - отключите автомат в щитке, "
    "если это безопасно"
)
EMERGENCY_PHONE_TEXT = (
    "🛠 Затем звоните в аварийную службу дома: {emergency_phone}. "
    "Оператор обязан ответить за 5 минут (ПП 416 п. 13)"
)
NO_EMERGENCY_PHONE_TEXT = (
    "🛠 Номер аварийной службы есть в квитанции и на доске объявлений в подъезде"
)
ORG_PHONE_TEXT = "🏢 Телефон УК: {org_phone}"
CALL_NOTE_TEXT = "📝 Запишите время звонка и номер заявки, который назовет диспетчер"


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


@inject
async def get_emergency(
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    **_: Any,
) -> dict[str, Any]:
    me = await profile_service.me(dialog_user_id(dialog_manager))
    residency = me.latest_residency
    org = None if residency is None else residency.org
    emergency_phone = None if org is None else org.emergency_phone
    org_phone = None if org is None or emergency_phone else org.phone.strip()
    return {
        "emergency_phone": emergency_phone and escape(emergency_phone),
        "emergency_copy": emergency_phone,
        "org_phone": org_phone and escape(org_phone),
        "org_copy": org_phone,
        "connected": residency is not None and residency.is_connected,
    }


menu_dialog = Dialog(
    Window(
        Multi(
            Const(MENU_TEXT, when=~F["address"]),
            Format(HOUSE_MENU_TEXT, when=F["address"]),
            Const(STAFF_TEXT, when=F["staff"]),
            sep="\n\n",
        ),
        MessageInput(on_meter_photo, content_types=[AttachmentType.IMAGE]),
        MessageInput(on_free_text),
        SwitchTo(EMERGENCY, id="emergency", state=Menu.emergency),
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
        WebApp(
            Const(CABINET_BUTTON),
            Format("{bot_username}"),
            payload=Const(app_payload(ADMIN_APP_PATH)),
            when=F["staff"] & F["bot_username"],
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
    Window(
        Multi(
            Const(EMERGENCY_TEXT),
            Format(EMERGENCY_PHONE_TEXT, when=F["emergency_phone"]),
            Const(NO_EMERGENCY_PHONE_TEXT, when=~F["emergency_phone"]),
            Format(ORG_PHONE_TEXT, when=F["org_phone"]),
            Const(CALL_NOTE_TEXT),
            sep="\n\n",
        ),
        MessageInput(on_free_text),
        CopyText(
            Const("📋 Номер аварийной службы"),
            Format("{emergency_copy}"),
            when=F["emergency_copy"],
        ),
        CopyText(
            Const("📋 Телефон УК"),
            Format("{org_copy}"),
            when=F["org_copy"],
        ),
        Start(
            Const("📝 Подать заявку"),
            id="emergency_request",
            state=NewRequest.category,
            when=F["connected"],
        ),
        TO_MENU,
        state=Menu.emergency,
        getter=get_emergency,
    ),
)
