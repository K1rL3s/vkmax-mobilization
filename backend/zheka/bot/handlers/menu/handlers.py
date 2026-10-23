import re
from datetime import UTC, datetime
from html import escape
from typing import Any

from dishka import FromDishka
from maxo import Bot
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback

from zheka.bot.cards import back_to_menu, refused, web_app_name
from zheka.bot.middlewares.user import dialog_user_id
from zheka.core.city_services import city_services
from zheka.core.enums import (
    CityServiceKind,
    NotificationCategory,
    NotificationLevel,
)
from zheka.core.errors import ZhekaError
from zheka.core.services.chats import NO_CHAT_TO_JOIN, ChatsService
from zheka.core.services.digest import DigestService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.profile import ProfileService
from zheka.core.texts import DIGEST_EMPTY, DIGEST_SUBSCRIBED

JOINING_CHAT = "⏳ Добавляю вас в чат «{title}», напишу, как получится"
RU_PHONE = re.compile(r"[78](\d{3})(\d{3})(\d{2})(\d{2})")
PHONE_CHARS = re.compile(r"[\d\s()+-]+")


def _pretty_phone(phone: str) -> str:
    if PHONE_CHARS.fullmatch(phone) is None:
        return phone
    match = RU_PHONE.fullmatch(re.sub(r"\D", "", phone))
    return phone if match is None else "+7 ({}) {}-{}-{}".format(*match.groups())


@inject
async def get_menu(
    bot: Bot,
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    chats_service: FromDishka[ChatsService],
    **_: Any,
) -> dict[str, Any]:
    user_id = dialog_user_id(dialog_manager)
    me = await profile_service.me(user_id)
    residency = me.latest_residency
    offer = (
        None
        if residency is None
        else await chats_service.join_offer(user_id, residency.house.id)
    )
    return {
        "bot_username": web_app_name(bot),
        "address": None if residency is None else escape(residency.house.address),
        "staff": me.is_staff,
        "can_join_chat": offer is not None and not offer.joined,
        "chat_link": offer.link if offer is not None and offer.joined else None,
    }


@inject
async def on_join_chat(
    callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    chats_service: FromDishka[ChatsService],
) -> None:
    user_id = dialog_user_id(dialog_manager)
    residency = (await profile_service.me(user_id)).latest_residency
    if residency is None:
        await callback.callback_answer(notification=NO_CHAT_TO_JOIN)
        return
    try:
        offer = await chats_service.request_join(user_id, residency.house.id)
    except ZhekaError as error:
        await refused(callback, error)
        return
    await callback.callback_answer(
        notification=JOINING_CHAT.format(title=offer.title),
    )


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
        "emergency_phone": emergency_phone and escape(_pretty_phone(emergency_phone)),
        "emergency_copy": emergency_phone,
        "org_phone": org_phone and escape(_pretty_phone(org_phone)),
        "org_copy": org_phone,
        "connected": residency is not None and residency.is_connected,
    }


@inject
async def get_contacts(
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    **_: Any,
) -> dict[str, Any]:
    me = await profile_service.me(dialog_user_id(dialog_manager))
    residency = me.latest_residency
    if residency is None:
        return {"address": None, "contacts": _contact("Экстренные службы", "112")}
    org = residency.org
    emergency_phone = None if org is None else org.emergency_phone
    org_phone = None if org is None else org.phone.strip() or None
    services = city_services(residency.house.region, residency.house.city)
    lines = [
        _contact("Аварийная служба дома", emergency_phone)
        if emergency_phone
        else "<b>Аварийная служба дома</b> - номер в квитанции и на стенде в подъезде",
        *([] if org is None or org_phone is None else [_contact(org.name, org_phone)]),
        *(
            _contact(service.name, service.phone, service.hours)
            for service in services
            if service.kind is not CityServiceKind.GZHI
        ),
        *(
            _contact(service.name, service.phone, service.hours, "жалоба на УК")
            for service in services
            if service.kind is CityServiceKind.GZHI
        ),
        _contact("Экстренные службы", "112"),
    ]
    return {
        "address": escape(residency.house.address),
        "contacts": "\n\n".join(lines),
        "emergency_copy": emergency_phone,
        "org_copy": org_phone,
    }


def _contact(name: str, phone: str, *notes: str | None) -> str:
    return " - ".join(
        [
            f"<b>{escape(name)}</b>",
            escape(_pretty_phone(phone)),
            *(escape(note.replace("\n", ", ")) for note in notes if note),
        ],
    )


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
