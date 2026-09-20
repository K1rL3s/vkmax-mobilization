from dishka import FromDishka
from maxo.dialogs import DialogManager, StartMode
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback

from zheka.bot.middlewares.user import USER_KEY
from zheka.bot.states import Menu
from zheka.core.consent import CONSENT_VERSION
from zheka.core.ids import UserId
from zheka.core.models import User
from zheka.core.services.profile import ProfileService


@inject
async def on_accept(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
) -> None:
    # accept_consent - единственное место, где версия согласия проверяется, и
    # согласие дают один раз, так что его лишние чтения не стоят второго метода
    user: User = dialog_manager.middleware_data[USER_KEY]
    await profile_service.accept_consent(UserId(user.id), CONSENT_VERSION)
    await dialog_manager.start(Menu.main, mode=StartMode.RESET_STACK)
