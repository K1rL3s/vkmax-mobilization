from typing import Any

from dishka import FromDishka
from maxo import Router
from maxo.dialogs import DialogManager, StartMode
from maxo.omit import is_not_defined
from maxo.routing.sentinels import UNHANDLED
from maxo.types import BotStarted

from zheka.bot.dialog_data import ConsentData, MenuData, OnboardingData
from zheka.bot.states import Consent, Menu, Onboarding
from zheka.core.deeplinks import Deeplink, DeeplinkKind, parse_deeplink
from zheka.core.enums import EventSource, EventType
from zheka.core.ids import UserId
from zheka.core.models import User
from zheka.core.services.events import EventsService
from zheka.core.services.flats import FlatsService
from zheka.core.services.orgs import OrgsService

router = Router(name=__name__)

REGISTER_NOTICE = "Регистрация управляющей компании открывается в приложении"
ORG_JOINED = "Вы в команде «{name}»"
FLAT_JOINED = "Квартира подтверждена"

# демо-нагрузки появятся в блоке 20: до тех пор они не наши, и апдейт с ними
# уходит дальше, в обычный /start
_SOURCE_BY_KIND = {
    DeeplinkKind.HOUSE: EventSource.CHAT,
    DeeplinkKind.ENTRANCE_QR: EventSource.QR,
    DeeplinkKind.ORG_INVITE: EventSource.DEEPLINK,
    DeeplinkKind.FLAT_INVITE: EventSource.DEEPLINK,
    DeeplinkKind.ORG_REGISTER: EventSource.DEEPLINK,
}


@router.bot_started()
async def deeplink_handler(
    update: BotStarted,
    dialog_manager: DialogManager,
    user: User,
    events_service: FromDishka[EventsService],
    orgs_service: FromDishka[OrgsService],
    flats_service: FromDishka[FlatsService],
) -> Any:
    # роутер стоит раньше commands_router, а maxo останавливается на первом
    # обработчике, вернувшем не UNHANDLED. Поэтому разобранная ссылка съедает
    # апдейт и пишет BOT_START со своим источником, а неразобранная обязана
    # вернуть UNHANDLED: вернув None, она оставила бы жителя с немым ботом
    payload = update.payload
    if is_not_defined(payload) or not payload:
        return UNHANDLED

    deeplink = parse_deeplink(payload)
    if deeplink is None or deeplink.kind not in _SOURCE_BY_KIND:
        return UNHANDLED

    await events_service.record(
        EventType.BOT_START,
        user_id=UserId(user.id),
        source=_SOURCE_BY_KIND[deeplink.kind].value,
    )
    await open_deeplink(
        deeplink,
        payload,
        dialog_manager,
        user,
        orgs_service,
        flats_service,
    )
    return None


async def open_deeplink(
    deeplink: Deeplink,
    payload: str,
    dialog_manager: DialogManager,
    user: User,
    orgs_service: OrgsService,
    flats_service: FlatsService,
) -> None:
    # согласие первее любой дороги в дом, а сама ссылка едет в start_data,
    # чтобы после нажатия «Согласен» житель попал туда, куда шел
    if user.consent_at is None:
        await dialog_manager.start(
            Consent.ask,
            data=ConsentData(payload=payload).to_data(),
            mode=StartMode.RESET_STACK,
        )
        return

    user_id = UserId(user.id)
    if deeplink.kind is DeeplinkKind.ORG_INVITE:
        membership = await orgs_service.activate_invite(user_id, deeplink.value)
        await _menu(dialog_manager, ORG_JOINED.format(name=membership.org.name))
    elif deeplink.kind is DeeplinkKind.FLAT_INVITE:
        await flats_service.activate_invite(user_id, deeplink.value)
        await _menu(dialog_manager, FLAT_JOINED)
    elif deeplink.kind is DeeplinkKind.ORG_REGISTER:
        # OpenAppButton умеет нести payload, но во фронте на startParam ничего
        # не роутится - он только классифицирует источник открытия, поэтому
        # код пока вводится в приложении руками
        await _menu(dialog_manager, REGISTER_NOTICE)
    else:
        await _start_house(deeplink, dialog_manager)


async def _start_house(deeplink: Deeplink, dialog_manager: DialogManager) -> None:
    # qr_<дом>_<подъезд>: parse_deeplink режет строку один раз, подъезд остается
    # внутри value. Смазанная цифра на печатном коде не должна ронять вход -
    # такая ссылка вырождается в обычный вход в дом
    house_id, _, entrance = deeplink.value.partition("_")
    if not house_id.isdigit():
        await dialog_manager.start(Onboarding.method, mode=StartMode.RESET_STACK)
        return

    await dialog_manager.start(
        Onboarding.flat,
        data=OnboardingData(
            house_id=int(house_id),
            entrance=int(entrance) if entrance.isdigit() else None,
            source=_SOURCE_BY_KIND[deeplink.kind],
        ).to_data(),
        mode=StartMode.RESET_STACK,
    )


async def _menu(dialog_manager: DialogManager, notice: str) -> None:
    await dialog_manager.start(
        Menu.main,
        data=MenuData(notice=notice).to_data(),
        mode=StartMode.RESET_STACK,
    )
