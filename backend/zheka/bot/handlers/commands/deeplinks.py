from html import escape
from typing import Any

from dishka import FromDishka
from maxo import Router
from maxo.dialogs import DialogManager, ShowMode, StartMode
from maxo.omit import is_not_defined
from maxo.routing.sentinels import UNHANDLED
from maxo.types import BotStarted

from zheka.bot.cards import back_to_menu
from zheka.bot.dialog_data import ConsentData, OnboardingData
from zheka.bot.states import Consent, Onboarding
from zheka.core.deeplinks import Deeplink, DeeplinkKind, parse_deeplink
from zheka.core.enums import EventType, OrgRole
from zheka.core.errors import ZhekaError
from zheka.core.models import User
from zheka.core.services.demo import DemoService, demo_flat_number
from zheka.core.services.events import EventsService
from zheka.core.services.flats import FlatsService
from zheka.core.services.orgs import OrgsService

router = Router(name=__name__)

REGISTER_NOTICE = "🏢 Регистрация управляющей компании открывается в приложении"
ORG_JOINED = "🎉 Вы в команде «{name}»"
FLAT_JOINED = "✅ Квартира подтверждена"
DEMO_DATA_NOTE = "\nℹ️ Организация и ее данные модельные, адреса домов настоящие"
DEMO_ADMIN_NOTICE = (
    "🎟 Демо-доступ открыт: вы администратор {org}. Кабинет УК с командой и "
    "настройками - в приложении" + DEMO_DATA_NOTE
)
DEMO_STAFF_NOTICE = (
    "🎟 Демо-доступ открыт: вы сотрудник {org}. Кабинет УК - в приложении"
    + DEMO_DATA_NOTE
)
DEMO_RESIDENT_NOTICE = (
    "🎟 Демо-доступ открыт: ваша квартира {flat}, {address}, дом обслуживает "
    "{org}. Передайте показания за этот месяц в приложении" + DEMO_DATA_NOTE
)

_DEMO_STAFF = {
    DeeplinkKind.DEMO_ADMIN: (OrgRole.ADMIN, DEMO_ADMIN_NOTICE),
    DeeplinkKind.DEMO_STAFF: (OrgRole.EMPLOYEE, DEMO_STAFF_NOTICE),
}
_HOUSE_KINDS = (DeeplinkKind.HOUSE, DeeplinkKind.ENTRANCE_QR)


@router.bot_started()
async def deeplink_handler(
    update: BotStarted,
    dialog_manager: DialogManager,
    user: User,
    events_service: FromDishka[EventsService],
    orgs_service: FromDishka[OrgsService],
    flats_service: FromDishka[FlatsService],
    demo_service: FromDishka[DemoService],
) -> Any:
    payload = update.payload
    if is_not_defined(payload) or not payload:
        return UNHANDLED

    deeplink = parse_deeplink(payload)
    if deeplink is None:
        return UNHANDLED

    dialog_manager.show_mode = ShowMode.SEND
    source = deeplink.source
    await events_service.record(
        EventType.BOT_START,
        user_id=user.id,
        source=source.value,
    )
    await open_deeplink(
        deeplink,
        payload,
        dialog_manager,
        user,
        orgs_service,
        flats_service,
        demo_service,
    )
    return None


async def open_deeplink(
    deeplink: Deeplink,
    payload: str,
    dialog_manager: DialogManager,
    user: User,
    orgs_service: OrgsService,
    flats_service: FlatsService,
    demo_service: DemoService,
) -> None:
    if user.consent_at is None:
        await dialog_manager.start(
            Consent.ask,
            data=ConsentData(payload=payload).to_data(),
            mode=StartMode.RESET_STACK,
        )
        return

    user_id = user.id
    try:
        if deeplink.kind is DeeplinkKind.ORG_INVITE:
            membership = await orgs_service.activate_invite(user_id, deeplink.value)
            notice = ORG_JOINED.format(name=escape(membership.org.name))
            await back_to_menu(dialog_manager, notice)
        elif deeplink.kind is DeeplinkKind.FLAT_INVITE:
            await flats_service.activate_invite(user_id, deeplink.value)
            await back_to_menu(dialog_manager, FLAT_JOINED)
        elif deeplink.kind is DeeplinkKind.ORG_REGISTER:
            await back_to_menu(dialog_manager, REGISTER_NOTICE)
        elif deeplink.kind in _HOUSE_KINDS:
            await _start_house(deeplink, dialog_manager)
        elif deeplink.kind is DeeplinkKind.DEMO_RESIDENT:
            org, residency = await demo_service.settle(user_id, int(deeplink.value))
            notice = DEMO_RESIDENT_NOTICE.format(
                flat=demo_flat_number(user_id),
                address=escape(residency.house.address),
                org=escape(org.name),
            )
            await back_to_menu(dialog_manager, notice)
        else:
            role, template = _DEMO_STAFF[deeplink.kind]
            access = await demo_service.join(user_id, int(deeplink.value), role)
            notice = template.format(org=escape(access.org.name))
            await back_to_menu(dialog_manager, notice)
    except ZhekaError as error:
        await back_to_menu(dialog_manager, str(error))


async def _start_house(deeplink: Deeplink, dialog_manager: DialogManager) -> None:
    house_id, _, entrance = deeplink.value.partition("_")
    if not house_id.isdigit():
        await dialog_manager.start(Onboarding.method, mode=StartMode.RESET_STACK)
        return

    await dialog_manager.start(
        Onboarding.flat,
        data=OnboardingData(
            house_id=int(house_id),
            entrance=int(entrance) if entrance.isdigit() else None,
            source=deeplink.source,
        ).to_data(),
        mode=StartMode.RESET_STACK,
    )
