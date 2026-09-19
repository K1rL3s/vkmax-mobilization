from maxo import Router
from maxo.routing.filters import CommandStart
from maxo.types import BotStarted, MessageCreated
from maxo.utils.builders import KeyboardBuilder

router = Router(name=__name__)

GREETING = (
    "Привет! Я Жэка Коммуналкин.\n\n"
    "Подаю заявки в УК, показываю начисления и собираю показания счётчиков. "
    "Открывай приложение, чтобы найти свой дом."
)


@router.bot_started()
async def bot_started_handler(update: BotStarted) -> None:
    await greet(update)


@router.message_created(CommandStart())
async def start_command_handler(update: MessageCreated) -> None:
    await greet(update)


async def greet(update: BotStarted | MessageCreated) -> None:
    keyboard = KeyboardBuilder()
    username = update.bot.state.info.username
    if username:
        keyboard.add_open_app(text="Открыть приложение", web_app=username)

    await update.send_message(
        text=GREETING,
        keyboard=keyboard.build() or None,
        notify=False,
    )
