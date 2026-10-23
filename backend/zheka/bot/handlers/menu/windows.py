from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import MessageInput
from maxo.dialogs.widgets.kbd import (
    Button,
    CopyText,
    Start,
    SwitchTo,
    Url,
    WebApp,
)
from maxo.dialogs.widgets.text import Const, Format, Multi
from maxo.enums import AttachmentType

from zheka.bot.cards import EMERGENCY, TO_MENU, app_payload
from zheka.bot.handlers.fallback import on_free_text
from zheka.bot.handlers.menu.handlers import (
    get_contacts,
    get_digest,
    get_emergency,
    get_menu,
    on_digest_subscribe,
    on_join_chat,
)
from zheka.bot.handlers.meter_photo.handlers import on_meter_photo
from zheka.bot.states import Menu, NewRequest, Onboarding
from zheka.core.deeplinks import ADMIN_APP_PATH
from zheka.core.texts import CABINET_BUTTON, DIGEST_BUTTON, DIGEST_SUBSCRIBE, OPEN_APP

GREETING = "👋 Жэка Коммуналкин на связи"
MENU_TEXT = (
    f"{GREETING}\n\n"
    "Подаю заявки в УК, показываю начисления и собираю показания счетчиков. "
    "Начните с поиска своего дома - здесь или в приложении"
)
HOUSE_MENU_TEXT = (
    f"{GREETING}\n\n"
    "🏢 {address}\n\n"
    "📝 Заявку можно подать здесь, показания, начисления и опросы - в приложении\n"
    "А можно просто написать, что случилось, - я оформлю заявку"
)
STAFF_TEXT = "🧑‍💼 Кабинет УК - в приложении"
EMERGENCY_TEXT = (
    "🚨 <b>Что делать в аварийной ситуации</b>\n\n"
    "<b>Пожар, дым или угроза жизни</b>\n"
    "Немедленно звоните <b>112</b>\n\n"
    "🔥 <b>Запах газа</b>\n"
    "Не включайте и не выключайте свет и электроприборы, не зажигайте огонь. "
    "Откройте окна, покиньте помещение и позвоните <b>104</b> или <b>112</b> "
    "из безопасного места\n\n"
    "💧 <b>Протечка воды</b>\n"
    "Если это безопасно, перекройте подачу воды к месту протечки. "
    "Не прикасайтесь к электроприборам мокрыми руками\n\n"
    "⚡️ <b>Искрит проводка или пахнет горелой изоляцией</b>\n"
    "Отключите электричество автоматом в щитке, если это безопасно. "
    "При появлении дыма или огня звоните <b>112</b>"
)
EMERGENCY_PHONE_TEXT = "<b>Аварийная служба:</b>\n<b>{emergency_phone}</b>"
EMERGENCY_NO_PHONE_TEXT = (
    "<b>Аварийная служба</b>\n"
    "Номер указан в квитанции и на информационном стенде в подъезде"
)
EMERGENCY_ORG_PHONE_TEXT = "<b>Телефон управляющей компании:</b>\n<b>{org_phone}</b>"
CALL_NOTE_TEXT = (
    "📝 <b>При обращении к диспетчеру</b>\n"
    "Сообщите адрес и опишите проблему. Запишите время звонка и номер заявки"
)
CONTACTS_BUTTON = "📞 Куда звонить"
CONTACTS_TEXT = "📞 <b>Куда звонить</b>\n\n🏢 {address}\n\n{contacts}"

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
        SwitchTo(
            Const(CONTACTS_BUTTON),
            id="contacts",
            state=Menu.contacts,
            when=F["address"],
        ),
        Button(
            Const("💬 Чат дома"),
            id="join_chat",
            on_click=on_join_chat,
            when=F["can_join_chat"],
        ),
        Url(
            Const("💬 Чат дома"),
            Format("{chat_link}"),
            when=F["chat_link"],
        ),
        SwitchTo(
            Const(DIGEST_BUTTON),
            id="digest",
            state=Menu.digest,
            when=F["address"],
        ),
        WebApp(
            Const(OPEN_APP),
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
            Const(EMERGENCY_NO_PHONE_TEXT, when=~F["emergency_phone"]),
            Format(EMERGENCY_ORG_PHONE_TEXT, when=F["org_phone"]),
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
    Window(
        Format("{digest}"),
        MessageInput(on_free_text),
        Button(
            Const(DIGEST_SUBSCRIBE),
            id="digest_on",
            on_click=on_digest_subscribe,
            when=F["can_subscribe"],
        ),
        TO_MENU,
        state=Menu.digest,
        getter=get_digest,
    ),
    Window(
        Format(CONTACTS_TEXT),
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
        TO_MENU,
        state=Menu.contacts,
        getter=get_contacts,
    ),
)
