from dishka import FromDishka
from maxo import Router
from maxo.dialogs import DialogManager, StartMode
from maxo.routing.filters import Command, CommandStart
from maxo.types import BotStarted, MessageCreated

from zheka.bot.states import entry_state
from zheka.core.enums import EventType
from zheka.core.ids import UserId
from zheka.core.models import User
from zheka.core.services.events import EventsService

router = Router(name=__name__)

HELP_TEXT = (
    "Команды:\n"
    "/start - открыть меню\n"
    "/help - эта справка\n\n"
    "Заявки, начисления и показания счётчиков живут в приложении - "
    "кнопка под меню."
)


@router.bot_started()
async def bot_started_handler(
    _update: BotStarted,
    dialog_manager: DialogManager,
    user: User,
    events_service: FromDishka[EventsService],
) -> None:
    await open_entry_window(dialog_manager, user, events_service)


@router.message_created(CommandStart())
async def start_command_handler(
    _update: MessageCreated,
    dialog_manager: DialogManager,
    user: User,
    events_service: FromDishka[EventsService],
) -> None:
    await open_entry_window(dialog_manager, user, events_service)


@router.message_created(Command("help"))
async def help_handler(update: MessageCreated) -> None:
    await update.answer_text(HELP_TEXT, notify=False)


async def open_entry_window(
    dialog_manager: DialogManager,
    user: User,
    events_service: EventsService,
) -> None:
    # единственное место, где пишется BOT_START: у апдейта без состояния
    # старта нет, а геттер окна перерисовывается на каждое нажатие
    await events_service.record(
        EventType.BOT_START,
        user_id=UserId(user.id),
        source="direct",
    )
    await dialog_manager.start(entry_state(user), mode=StartMode.RESET_STACK)
