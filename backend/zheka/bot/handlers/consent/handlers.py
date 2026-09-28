from typing import Any

from dishka import FromDishka
from maxo import Bot
from maxo.dialogs import DialogManager, ShowMode, StartMode
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback

from zheka.bot.cards import web_app_name
from zheka.bot.dialog_data import ConsentData
from zheka.bot.handlers.commands.deeplinks import open_deeplink
from zheka.bot.middlewares.user import USER_KEY
from zheka.bot.states import Menu
from zheka.core.consent import CONSENT_VERSION
from zheka.core.deeplinks import parse_deeplink
from zheka.core.enums import EventSource
from zheka.core.models import User
from zheka.core.services.admin_requests import AdminRequestsService
from zheka.core.services.chairman import ChairmanService
from zheka.core.services.demo import DemoService
from zheka.core.services.flats import FlatsService
from zheka.core.services.orgs import OrgsService
from zheka.core.services.profile import ProfileService


@inject
async def on_accept(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    orgs_service: FromDishka[OrgsService],
    flats_service: FromDishka[FlatsService],
    demo_service: FromDishka[DemoService],
    admin_requests_service: FromDishka[AdminRequestsService],
    chairman_service: FromDishka[ChairmanService],
) -> None:
    user: User = dialog_manager.middleware_data[USER_KEY]
    payload = ConsentData.load_start(dialog_manager).payload or ""
    deeplink = parse_deeplink(payload)
    me = await profile_service.accept_consent(
        user.id,
        CONSENT_VERSION,
        EventSource.DIRECT if deeplink is None else deeplink.source,
    )

    with ConsentData.proxy(dialog_manager) as data:
        data.given = True
    await dialog_manager.show()
    dialog_manager.show_mode = ShowMode.SEND

    if deeplink is not None:
        await open_deeplink(
            deeplink,
            payload,
            dialog_manager,
            me.user,
            orgs_service,
            flats_service,
            demo_service,
            admin_requests_service,
            chairman_service,
        )
        return

    await dialog_manager.start(Menu.main, mode=StartMode.RESET_STACK)


async def get_consent(
    bot: Bot,
    dialog_manager: DialogManager,
    **_: Any,
) -> dict[str, Any]:
    return {
        "bot_username": web_app_name(bot),
        "given": ConsentData.load(dialog_manager).given,
    }
