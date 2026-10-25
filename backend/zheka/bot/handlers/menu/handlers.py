import re
from datetime import UTC, datetime
from html import escape
from typing import Any

from dishka import FromDishka
from maxo import Bot
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.kbd import Button, Select
from maxo.types import MessageCallback

from zheka.bot.cards import app_payload, back_to_menu, refused, web_app_name
from zheka.bot.dialog_data import NewRequestData, ResponsibilityData
from zheka.bot.handlers.meter_photo.handlers import MONTHS
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import Menu, NewRequest
from zheka.core.charges import LineDelta
from zheka.core.city_services import CityService, city_services
from zheka.core.deeplinks import (
    CHARGES_APP_PATH,
    charge_app_path,
    flat_confirmation_app_path,
)
from zheka.core.enums import (
    CATEGORY_RULES,
    SERVICE_LABELS,
    CityServiceKind,
    NotificationCategory,
    NotificationLevel,
)
from zheka.core.errors import ZhekaError
from zheka.core.responsibility import LEAVES, SPOTS, Leaf, Spot, Verdict
from zheka.core.services.charges import BillChange, ChargesService
from zheka.core.services.chats import NO_CHAT_TO_JOIN, ChatsService
from zheka.core.services.digest import DigestService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.profile import ProfileService
from zheka.core.texts import DIGEST_EMPTY, DIGEST_SUBSCRIBED

JOINING_CHAT = "⏳ Добавляю вас в чат «{title}», напишу, как получится"
RU_PHONE = re.compile(r"[78](\d{3})(\d{3})(\d{2})(\d{2})")
PHONE_CHARS = re.compile(r"[\d\s()+-]+")
VERDICT_TITLES = {
    Verdict.MANAGEMENT: "🏢 <b>Отвечает УК</b>",
    Verdict.OWNER: "🔧 <b>Отвечает собственник квартиры</b>",
    Verdict.UTILITY: "🏭 <b>Отвечает ресурсная организация</b>",
    Verdict.EMERGENCY: "🚨 <b>Звоните 112</b>",
}
OWNER_HINT = "💡 УК может помочь платно: спросите у нее, сколько стоит вызов мастера"
SPOTS_TEXT = (
    "📞 <b>Кто отвечает и куда звонить?</b>\n\n"
    "Где сломалось? Подскажу, кто должен чинить и куда звонить"
)
SPOT_ITEMS = {
    "spots": [{"id": spot.value, "label": label} for spot, label in SPOTS.items()],
}
UTILITY_NO_PHONE = "📞 Телефон организации - в квитанции. При угрозе жизни звоните 112"
ORG_VERDICTS = frozenset({Verdict.MANAGEMENT, Verdict.OWNER})


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
        "sees_bill": residency is not None
        and residency.resident.verified_flat_id is not None
        and residency.resident.can_see_charges,
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


async def on_spot(
    _callback: MessageCallback,
    _select: Select[str],
    dialog_manager: DialogManager,
    spot: str,
) -> None:
    if spot not in SPOTS:
        return
    with ResponsibilityData.proxy(dialog_manager) as data:
        data.spot = Spot(spot)
    await dialog_manager.switch_to(Menu.who_subject)


async def get_subjects(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    spot = ResponsibilityData.load(dialog_manager).spot
    return {
        "spot": "" if spot is None else SPOTS[spot],
        "subjects": [
            {"id": key, "label": leaf.label}
            for key, leaf in LEAVES.items()
            if leaf.spot is spot
        ],
    }


async def on_subject(
    _callback: MessageCallback,
    _select: Select[str],
    dialog_manager: DialogManager,
    key: str,
) -> None:
    if key not in LEAVES:
        return
    with ResponsibilityData.proxy(dialog_manager) as data:
        data.leaf = key
    await dialog_manager.switch_to(Menu.who_verdict)


@inject
async def get_verdict(
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    **_: Any,
) -> dict[str, Any]:
    leaf = ResponsibilityData.load(dialog_manager).chosen
    if leaf is None:
        return {"verdict": SPOTS_TEXT, "category": None}
    residency = (
        await profile_service.me(dialog_user_id(dialog_manager))
    ).latest_residency
    org = (
        None if residency is None or leaf.verdict not in ORG_VERDICTS else residency.org
    )
    emergency_phone = (
        None if org is None or leaf.verdict is Verdict.OWNER else org.emergency_phone
    )
    org_phone = None if org is None else org.phone.strip() or None
    services = (
        []
        if residency is None or leaf.service is None
        else [
            service
            for service in city_services(residency.house.region, residency.house.city)
            if service.kind is leaf.service
        ]
    )
    return {
        "verdict": "\n\n".join(
            [
                VERDICT_TITLES[leaf.verdict],
                leaf.label,
                f"⚖️ {leaf.basis}",
                *_verdict_lines(leaf, services),
                *(
                    [f"📞 {_contact('Аварийная служба дома', emergency_phone)}"]
                    if emergency_phone
                    else []
                ),
                *(
                    [f"📞 {_contact(org.name, org_phone)}"]
                    if org is not None and org_phone is not None
                    else []
                ),
            ],
        ),
        "category": leaf.category,
        "emergency_copy": emergency_phone,
        "org_copy": org_phone,
    }


def _verdict_lines(leaf: Leaf, services: list[CityService]) -> list[str]:
    phones = [
        f"📞 {_contact(service.name, service.phone, service.hours)}"
        for service in services
    ]
    match leaf.verdict:
        case Verdict.MANAGEMENT if leaf.category is not None:
            rule = CATEGORY_RULES[leaf.category]
            lines = [f"⏰ Срок - {rule.deadline_text}"]
            if rule.react_text is not None:
                lines.insert(0, f"⏳ Локализовать аварию - {rule.react_text}")
            if rule.basis is not None:
                lines.append(f"📜 {rule.basis}")
            return ["\n".join(lines)]
        case Verdict.OWNER:
            return [OWNER_HINT]
        case Verdict.UTILITY:
            return phones or [UTILITY_NO_PHONE]
        case Verdict.EMERGENCY:
            return [*phones, f"📞 {_contact('Экстренные службы', '112')}"]
    return []


@inject
async def on_responsibility_request(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
) -> None:
    leaf = ResponsibilityData.load(dialog_manager).chosen
    residency = (
        await profile_service.me(dialog_user_id(dialog_manager))
    ).latest_residency
    if (
        leaf is None
        or leaf.category is None
        or residency is None
        or not residency.is_connected
    ):
        await dialog_manager.start(NewRequest.category)
        return
    draft = NewRequestData(
        house_id=residency.house.id,
        flat_id=None if residency.flat is None else residency.flat.id,
        category=leaf.category,
        place=leaf.place,
    )
    await dialog_manager.start(NewRequest.description, data=draft.to_data())


BILL_NOT_VERIFIED = "🔐 Начисления видны после подтверждения квартиры"
BILL_TENANT = "🔐 Начисления видит собственник квартиры"
BILL_EMPTY = "📄 Начислений пока нет"
BILL_FIRST = "📄 Первый месяц в истории квартиры - сравнить пока не с чем"
BILL_SAME = "🟰 Сумма не изменилась"
BILL_LINES = 4


@inject
async def get_bill(
    bot: Bot,
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    charges_service: FromDishka[ChargesService],
    **_: Any,
) -> dict[str, Any]:
    user_id = dialog_user_id(dialog_manager)
    residency = (await profile_service.me(user_id)).latest_residency
    resident = None if residency is None else residency.resident
    flat_id = None if resident is None else resident.verified_flat_id
    data: dict[str, Any] = {
        "bot_username": web_app_name(bot),
        "find_house": resident is None,
        "verify_payload": None,
        "charge_payload": None,
        "charges_payload": None,
    }
    if resident is None or flat_id is None:
        verify = None if resident is None else flat_confirmation_app_path(resident.id)
        return data | {
            "bill": BILL_NOT_VERIFIED,
            "verify_payload": verify and app_payload(verify),
        }
    if not resident.can_see_charges:
        return data | {"bill": BILL_TENANT}
    change = await charges_service.latest_change(flat_id, user_id)
    data["charges_payload"] = app_payload(CHARGES_APP_PATH)
    if change is None:
        return data | {"bill": BILL_EMPTY}
    return data | {
        "bill": _bill_text(change),
        "charge_payload": app_payload(charge_app_path(change.charge.id)),
    }


def _bill_text(change: BillChange) -> str:
    charge = change.charge
    period = f"{MONTHS[charge.period.month - 1].capitalize()} {charge.period.year}"
    head = f"💸 <b>{period}: {_rubles(charge.total)}</b>"
    if change.previous_charge is None:
        return f"{head}\n\n{BILL_FIRST}"
    delta = change.breakdown.delta
    total = (
        f"{'📈' if delta > 0 else '📉'} {_rubles(delta, signed=True)} к прошлому месяцу"
        if delta
        else BILL_SAME
    )
    lines = [line for line in change.breakdown.lines if line.delta][:BILL_LINES]
    return "\n\n".join(
        filter(None, [head, total, "\n".join(map(_bill_line, lines))]),
    )


def _bill_line(line: LineDelta) -> str:
    if line.kind == "appeared":
        detail = "новая строка"
    elif line.kind == "disappeared":
        detail = "строки больше нет"
    else:
        detail = ", ".join(
            f"{name} {_rubles(effect, signed=True)}"
            for name, effect in (
                ("тариф", line.tariff_effect),
                ("расход", line.volume_effect),
            )
            if effect
        )
    label = SERVICE_LABELS[line.service]
    return f"🔸 {label} {_rubles(line.delta, signed=True)}: {detail}"


def _rubles(kopecks: int, *, signed: bool = False) -> str:
    whole, cents = divmod(abs(kopecks), 100)
    sign = "-" if kopecks < 0 else "+" if signed and kopecks else ""
    amount = f"{whole:,}".replace(",", " ")
    return f"{sign}{amount},{cents:02d} ₽" if cents else f"{sign}{amount} ₽"


@inject
async def get_spots(
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    **_: Any,
) -> dict[str, Any]:
    me = await profile_service.me(dialog_user_id(dialog_manager))
    return {**SPOT_ITEMS, "address": me.latest_residency is not None}
