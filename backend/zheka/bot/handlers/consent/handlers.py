from dishka import FromDishka
from maxo.dialogs import DialogManager, StartMode
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback

from zheka.bot.dialog_data import ConsentData
from zheka.bot.handlers.commands.deeplinks import open_deeplink
from zheka.bot.middlewares.user import USER_KEY
from zheka.bot.states import Menu
from zheka.core.consent import CONSENT_VERSION
from zheka.core.deeplinks import parse_deeplink
from zheka.core.ids import UserId
from zheka.core.models import User
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
) -> None:
    # accept_consent - единственное место, где версия согласия проверяется, и
    # согласие дают один раз, так что его лишние чтения не стоят второго метода
    user: User = dialog_manager.middleware_data[USER_KEY]
    me = await profile_service.accept_consent(UserId(user.id), CONSENT_VERSION)

    # диплинк, приведший сюда, ждет в start_data: без него житель после
    # «Согласен» уезжал бы в меню и терял то, на что нажал
    payload = ConsentData.load_start(dialog_manager).payload
    if payload is not None:
        deeplink = parse_deeplink(payload)
        if deeplink is not None:
            await open_deeplink(
                deeplink,
                payload,
                dialog_manager,
                me.user,
                orgs_service,
                flats_service,
                demo_service,
            )
            return

    await dialog_manager.start(Menu.main, mode=StartMode.RESET_STACK)
