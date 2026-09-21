from maxo import Router
from maxo.dialogs import DialogManager, StartMode
from maxo.types import MessageCreated

from zheka.bot.states import entry_state
from zheka.core.models import User

router = Router(name=__name__)


@router.message_created()
async def no_state_handler(
    _update: MessageCreated, dialog_manager: DialogManager, user: User
) -> None:
    # BOT_START здесь не пишется: апдейт без состояния - не старт
    await dialog_manager.start(entry_state(user), mode=StartMode.RESET_STACK)
