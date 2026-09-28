from maxo import Router
from maxo.dialogs import DialogManager, StartMode
from maxo.dialogs.widgets.input import MessageInput
from maxo.types import MessageCreated

from zheka.bot.dialog_data import NewRequestData
from zheka.bot.middlewares.user import USER_KEY
from zheka.bot.states import NewRequest, entry_state
from zheka.core.models import User

router = Router(name=__name__)


@router.message_created()
async def no_state_handler(
    update: MessageCreated,
    dialog_manager: DialogManager,
    user: User,
) -> None:
    draft = NewRequestData.from_free_text(update.message.body)
    if user.consent_at is None or draft is None:
        await dialog_manager.start(entry_state(user), mode=StartMode.RESET_STACK)
        return
    await dialog_manager.start(
        NewRequest.category,
        mode=StartMode.RESET_STACK,
        data=draft.to_data(),
    )


async def on_free_text(
    update: MessageCreated,
    _widget: MessageInput,
    dialog_manager: DialogManager,
) -> None:
    user: User = dialog_manager.middleware_data[USER_KEY]
    draft = NewRequestData.from_free_text(update.message.body)
    if user.consent_at is None:
        await dialog_manager.start(entry_state(user), mode=StartMode.RESET_STACK)
    elif draft is not None:
        await dialog_manager.start(
            NewRequest.category,
            mode=StartMode.RESET_STACK,
            data=draft.to_data(),
        )
