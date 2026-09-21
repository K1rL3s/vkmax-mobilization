from dishka import FromDishka
from maxo import Router
from maxo.dialogs import DialogManager, StartMode
from maxo.routing.filters import Command, CommandStart
from maxo.types import BotStarted, MessageCreated

from zheka.bot.states import entry_state
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import EventSource, EventType
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
SEEDING_TEXT = "Заполняю демо-данные, это займет до минуты"


@router.bot_started()
@router.message_created(CommandStart())
async def start_handler(
    _update: BotStarted | MessageCreated,
    dialog_manager: DialogManager,
    user: User,
    events_service: FromDishka[EventsService],
) -> None:
    # BOT_START пишут только этот обработчик и deeplink_handler, по разу на старт:
    # апдейт без состояния - не старт, а геттер окна перерисовывается на каждое нажатие
    await events_service.record(
        EventType.BOT_START,
        user_id=user.id,
        source=EventSource.DIRECT.value,
    )
    await dialog_manager.start(entry_state(user), mode=StartMode.RESET_STACK)


@router.message_created(Command("help"))
async def help_handler(update: MessageCreated) -> None:
    await update.answer_text(HELP_TEXT, notify=False)


# ponytail: нажать может кто угодно - сид трогает только базу без демо, но
# первый нажавший на свежем деплое запускает 30-дневное окно аналитики.
# Ограничить id владельца из конфига, если посторонний засеет раньше времени
@router.message_created(Command("seed"))
async def seed_handler(
    update: MessageCreated, user: User, publisher: FromDishka[TaskPublisher]
) -> None:
    # тысячи строк не укладываются в 30 секунд вебхука
    publisher.publish(TaskName.SEED_DEMO, user_id=int(user.id))
    await update.answer_text(SEEDING_TEXT, notify=False)
