from dishka import FromDishka
from maxo import Router
from maxo.routing.filters import CommandStart
from maxo.types import BotStarted, MessageCreated
from maxo.utils.builders import KeyboardBuilder

from zheka.config import MaxConfig

router = Router(name=__name__)

GREETING = (
    "Привет! Я Жэка Коммуналкин.\n\n"
    "Подаю заявки в УК, показываю начисления и собираю показания счётчиков. "
    "Открывай приложение, чтобы найти свой дом."
)


@router.bot_started()
async def bot_started_handler(
    update: BotStarted,
    config: FromDishka[MaxConfig],
) -> None:
    await greet(update, config)


@router.message_created(CommandStart())
async def start_command_handler(
    update: MessageCreated,
    config: FromDishka[MaxConfig],
) -> None:
    await greet(update, config)


async def greet(update: BotStarted | MessageCreated, config: MaxConfig) -> None:
    keyboard = KeyboardBuilder()
    if config.miniapp_url:
        keyboard.add_open_app(text="Открыть приложение", web_app=config.miniapp_url)

    await update.send_message(
        text=GREETING,
        keyboard=keyboard.build() or None,
        notify=False,
    )
