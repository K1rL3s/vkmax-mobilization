from datetime import UTC, datetime
from html import escape
from typing import Any

from dishka import FromDishka
from magic_filter import F
from maxo import Bot
from maxo.dialogs import Dialog, DialogManager, Window
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import MessageInput
from maxo.dialogs.widgets.kbd import Button, CopyText, Start, SwitchTo, WebApp
from maxo.dialogs.widgets.text import Const, Format, Multi
from maxo.enums import AttachmentType
from maxo.types import MessageCallback

from zheka.bot.cards import EMERGENCY, TO_MENU, app_payload, back_to_menu, web_app_name
from zheka.bot.handlers.fallback import on_free_text
from zheka.bot.handlers.meter_photo.handlers import on_meter_photo
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import Menu, NewRequest, Onboarding
from zheka.core.deeplinks import ADMIN_APP_PATH
from zheka.core.enums import NotificationCategory, NotificationLevel
from zheka.core.services.digest import DigestService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.profile import ProfileService
from zheka.core.texts import (
    CABINET_BUTTON,
    DIGEST_BUTTON,
    DIGEST_EMPTY,
    DIGEST_SUBSCRIBE,
    DIGEST_SUBSCRIBED,
    NO_EMERGENCY_PHONE_TEXT,
    OPEN_APP,
    ORG_PHONE_TEXT,
)

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
    "🚨 Угроза жизни, пожар или дым - звоните 112\n\n"
    "🔥 Пахнет газом - не включайте свет и приборы, не зажигайте огонь, "
    "откройте окна, выйдите и звоните 104 или 112\n\n"
    "💧 Течет вода - перекройте кран на стояке или под раковиной, "
    "не трогайте приборы мокрыми руками\n\n"
    "⚡️ Искрит проводка или пахнет гарью - отключите автомат в щитке, "
    "если это безопасно"
)
EMERGENCY_PHONE_TEXT = (
    "🛠 Затем звоните в аварийную службу дома: {emergency_phone}. "
    "Оператор обязан ответить за 5 минут (ПП 416 п. 13)"
)
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


@inject
async def get_digest(
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    digest_service: FromDishka[DigestService],
    notifications_service: FromDishka[NotificationsService],
    **_: Any,
) -> dict[str, Any]:
    user_id = dialog_user_id(dialog_manager)
    residency = (await profile_service.me(user_id)).latest_residency
    digest = (
        None
        if residency is None
        else await digest_service.for_house(residency.house, datetime.now(UTC))
    )
    levels = await notifications_service.levels(user_id)
    return {
        "digest": digest or DIGEST_EMPTY,
        "can_subscribe": levels[NotificationCategory.DIGEST] is NotificationLevel.OFF,
    }


@inject
async def on_digest_subscribe(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    notifications_service: FromDishka[NotificationsService],
) -> None:
    await notifications_service.update(
        dialog_user_id(dialog_manager),
        {NotificationCategory.DIGEST: NotificationLevel.SILENT},
    )
    await back_to_menu(dialog_manager, DIGEST_SUBSCRIBED)


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
)
