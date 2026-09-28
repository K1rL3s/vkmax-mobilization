from dishka import FromDishka
from maxo.dialogs import DialogManager, StartMode
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback

from zheka.bot.middlewares.user import USER_KEY, dialog_user_id
from zheka.bot.states import entry_state
from zheka.core.models import User
from zheka.core.services.profile import ProfileService

FORGOTTEN_TEXT = "✅ Данные удалены. Чтобы вернуться, нажмите /start"


@inject
async def on_forget(
    callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
) -> None:
    await profile_service.forget(dialog_user_id(dialog_manager))
    await dialog_manager.reset_stack()
    await callback.answer_text(FORGOTTEN_TEXT, notify=False)


async def on_keep(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
) -> None:
    user: User = dialog_manager.middleware_data[USER_KEY]
    await dialog_manager.start(entry_state(user), mode=StartMode.RESET_STACK)
