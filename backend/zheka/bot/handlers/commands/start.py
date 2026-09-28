import logging
from datetime import UTC, datetime

from dishka import FromDishka
from maxo import Bot, Router
from maxo.dialogs import DialogManager, ShowMode, StartMode
from maxo.errors import MaxBotApiError, MaxBotNetworkError
from maxo.routing.filters import Command, CommandStart
from maxo.types import BotCommand, BotStarted, MessageCreated

from zheka.bot.states import Forget, entry_state
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import EventSource, EventType
from zheka.core.models import User
from zheka.core.services.events import EventsService
from zheka.core.services.reminders import RemindersService

logger = logging.getLogger(__name__)

router = Router(name=__name__)

HELP_TEXT = (
    "ℹ️ Команды\n"
    "/start - открыть меню\n"
    "/help - эта справка\n"
    "/delete - удалить мои данные\n\n"
    "💬 В чате дома, для председателя и сотрудников УК\n"
    "/pin - закрепить сообщение, ответом на него\n"
    "/unpin - открепить ответом на сообщение или номером из списка\n"
    "/repin - прислать список закрепленных заново\n\n"
    "📝 Заявку можно подать здесь, кнопкой в меню. Начисления, показания и опросы "
    "- в приложении"
)
SEEDING_TEXT = "⏳ Заполняю демо-данные, это займет до минуты"
DEMO_REMINDERS_TEXT = "🧪 Так приходят напоминания по расписанию"
CHAT_COMMANDS_ONLY = (
    "💬 Команды /pin, /unpin и /repin работают только в чате дома, "
    "и пользоваться ими могут председатель и сотрудники УК"
)
BOT_COMMANDS = [
    BotCommand(name="start", description="Открыть меню"),
    BotCommand(name="help", description="Справка по командам"),
    BotCommand(name="delete", description="Удалить мои данные"),
    BotCommand(name="pin", description="Закрепить сообщение в чате дома"),
    BotCommand(name="unpin", description="Открепить сообщение в чате дома"),
    BotCommand(name="repin", description="Прислать список закрепленных заново"),
]


@router.bot_started()  # type: ignore[arg-type]
@router.message_created(CommandStart())
async def start_handler(
    _: BotStarted | MessageCreated,
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


@router.message_created(Command("help"))
async def help_handler(update: MessageCreated) -> None:
    await update.answer_text(HELP_TEXT, notify=False)


@router.message_created(Command("seed"))
async def seed_handler(
    update: MessageCreated,
    user: User,
    publisher: FromDishka[TaskPublisher],
) -> None:
    reply = await update.answer_text(SEEDING_TEXT, notify=False)
    publisher.publish(
        TaskName.SEED_DEMO,
        user_id=int(user.id),
        mid=reply.body.mid,
        chat_id=reply.recipient.chat_id,
    )


@router.after_startup()
async def set_commands_handler(bot: Bot) -> None:
    try:
        await bot.edit_my_commands(commands=BOT_COMMANDS)
    except (MaxBotApiError, MaxBotNetworkError):
        logger.exception("Команды бота не установлены")


@router.message_created(Command("pin", "unpin", "repin"))
async def chat_command_handler(update: MessageCreated) -> None:
    await update.answer_text(CHAT_COMMANDS_ONLY, notify=False)


@router.message_created(Command("demo"))
async def demo_handler(
    update: MessageCreated,
    user: User,
    reminders_service: FromDishka[RemindersService],
) -> None:
    await update.answer_text(DEMO_REMINDERS_TEXT, notify=False)
    await reminders_service.demo(user.id, datetime.now(UTC))


@router.message_created(Command("delete"))
async def forget_handler(_: MessageCreated, dialog_manager: DialogManager) -> None:
    dialog_manager.show_mode = ShowMode.SEND
    await dialog_manager.start(Forget.confirm, mode=StartMode.RESET_STACK)
