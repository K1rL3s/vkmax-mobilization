import logging

from dishka import FromDishka
from maxo import Bot, Router
from maxo.dialogs import DialogManager, ShowMode, StartMode
from maxo.errors import MaxBotApiError, MaxBotNetworkError
from maxo.routing.filters import Command, CommandStart
from maxo.types import BotCommand, BotStarted, MessageCreated

from zheka.bot.states import entry_state
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import EventSource, EventType
from zheka.core.models import User
from zheka.core.services.events import EventsService

logger = logging.getLogger(__name__)

router = Router(name=__name__)

HELP_TEXT = (
    "ℹ️ Команды\n"
    "/start - открыть меню\n"
    "/help - эта справка\n\n"
    "💬 В чате дома, для председателя и сотрудников УК\n"
    "/pin - закрепить сообщение, ответом на него\n"
    "/unpin - открепить ответом на сообщение или номером из списка\n"
    "/repin - прислать список закрепленных заново\n\n"
    "📱 Заявки, начисления и показания счетчиков - в приложении, кнопка под меню"
)
SEEDING_TEXT = "⏳ Заполняю демо-данные, это займет до минуты"
CHAT_COMMANDS_ONLY = (
    "💬 Команды /pin, /unpin и /repin работают только в чате дома, "
    "и пользоваться ими могут председатель и сотрудники УК"
)
BOT_COMMANDS = [
    BotCommand(name="start", description="Открыть меню"),
    BotCommand(name="help", description="Справка по командам"),
    BotCommand(name="pin", description="Закрепить сообщение в чате дома"),
    BotCommand(name="unpin", description="Открепить сообщение в чате дома"),
    BotCommand(name="repin", description="Прислать список закрепленных заново"),
]


@router.bot_started()
async def bot_start_handler(
    _: BotStarted,
    dialog_manager: DialogManager,
    user: User,
    events_service: FromDishka[EventsService],
) -> None:
    dialog_manager.show_mode = ShowMode.SEND
    await events_service.record(
        EventType.BOT_START,
        user_id=user.id,
        source=EventSource.DIRECT.value,
    )
    await dialog_manager.start(entry_state(user), mode=StartMode.RESET_STACK)


@router.message_created(CommandStart())
async def start_message_handler(
    _: MessageCreated,
    dialog_manager: DialogManager,
    user: User,
    events_service: FromDishka[EventsService],
) -> None:
    await events_service.record(
        EventType.BOT_START,
        user_id=user.id,
        source=EventSource.DIRECT.value,
    )
    await dialog_manager.start(entry_state(user), mode=StartMode.RESET_STACK)


@router.message_created(Command("help"))
async def help_handler(update: MessageCreated) -> None:
    await update.answer_text(HELP_TEXT, notify=False)


@router.message_created(Command("seed"))
async def seed_handler(
    update: MessageCreated,
    user: User,
    publisher: FromDishka[TaskPublisher],
) -> None:
    publisher.publish(TaskName.SEED_DEMO, user_id=int(user.id))
    await update.answer_text(SEEDING_TEXT, notify=False)


@router.after_startup()
async def set_commands_handler(bot: Bot) -> None:
    try:
        await bot.edit_my_commands(commands=BOT_COMMANDS)
    except (MaxBotApiError, MaxBotNetworkError):
        logger.exception("Команды бота не установлены")


@router.message_created(Command("pin", "unpin", "repin"))
async def chat_command_handler(update: MessageCreated) -> None:
    await update.answer_text(CHAT_COMMANDS_ONLY, notify=False)
