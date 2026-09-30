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
    "💡 Что я умею\n\n"
    "🏠 Дом\n"
    "Найдите свой дом кнопкой «🔎 Найти дом» в меню: по адресу или по геолокации. "
    "Номер квартиры можно указать сразу или пропустить\n"
    "Заявки и показания принимает подключенный дом: тот, чья УК работает в Жэке\n\n"
    "📝 Заявки в УК\n"
    "«📝 Подать заявку»: категория, где проблема, описание, фото или видео "
    "(до 12 файлов), проверка и отправка\n"
    "Или просто напишите, что случилось, от 15 символов - я сам начну оформлять "
    "заявку. Фото с такой подписью станет вложением\n"
    "В ответ пришлю номер заявки, срок и норму, на которой он основан\n"
    "Сообщу о каждой смене статуса и ответе УК. На вопрос УК ответьте кнопкой "
    "«📝 Ответить»\n"
    "Пока работу не сдали на приемку, заявку можно отменить\n"
    "Сданную работу примите с оценкой или верните кнопкой «👎 Сделано плохо» - "
    "уйдет повторная заявка. Без ответа заявка закроется сама через 48 часов\n"
    "Срок прошел - напишу об этом. В карточке заявки в приложении можно попросить "
    "руководство УК вмешаться и получить готовую жалобу в ГЖИ\n\n"
    "🚨 Авария\n"
    "Кнопка «🚨 Авария» в меню: что сделать сразу и номер аварийной службы дома. "
    "Если в сообщении запах газа, дым или искры, сначала подскажу, куда звонить\n\n"
    "📟 Счетчики\n"
    "Пришлите сюда фото счетчика без подписи, и я приму показание: число можно "
    "проверить или написать вручную. Двухтарифный счетчик передается в приложении\n"
    "Напомню, когда откроется и будет закрываться прием показаний, и о сроке "
    "поверки\n\n"
    "📢 Новости дома\n"
    "Присылаю объявления УК, опросы, напоминания о записи на прием и запросы "
    "доступа в квартиру\n"
    "«📊 Сводка за неделю» в меню - главное по дому за 7 дней, ее можно получать "
    "по воскресеньям\n\n"
    "📱 В приложении\n"
    "Подтверждение квартиры, начисления, показания, опросы, запись на прием, "
    "карточка дома с контактами УК и настройки уведомлений\n\n"
    "🧑‍💼 Сотрудникам УК\n"
    "Кабинет УК открывается кнопкой в меню. Исполнитель ведет заявку здесь: "
    "«✅ Принял», «🚗 Выехал», «🏁 Готово» с фото результата или «🙅 Не могу»\n\n"
    "💬 Чат дома\n"
    "Сотрудник УК или председатель добавляет меня в группу MAX и привязывает ее "
    "к дому. Там я публикую объявления, карточки заявок и опросов и веду список "
    "закрепленных сообщений\n\n"
    "💬 Команды\n"
    "/start - открыть меню\n"
    "/help - эта справка\n"
    "/faq - частые вопросы\n"
    "/delete - удалить мои данные\n"
    "В чате дома, для председателя и сотрудников УК:\n"
    "/pin - закрепить сообщение, ответом на него\n"
    "/unpin - открепить ответом на сообщение или номером из списка\n"
    "/repin - прислать список закрепленных заново"
)
FAQ_TEXT = (
    "❓ Частые вопросы\n\n"
    "📝 Как подать заявку?\n"
    "Кнопкой «📝 Подать заявку» в меню или просто напишите, что случилось. "
    "В приложении есть та же форма\n\n"
    "⏰ Какой срок у заявки?\n"
    "Срок считается от подачи и приходит вместе с номером. Протечку должны "
    "локализовать за 30 минут с регистрации заявки и устранить не дольше 3 суток "
    "(ПП РФ № 416, п. 13). Вода - 4 часа, "
    "отопление - 16 часов, свет - 24 часа: допустимые перерывы по ПП РФ № 354, "
    "прил. 1. Ошибка в показаниях, спор по начислению и «Другое» - 10 рабочих "
    "дней (ПП РФ № 354, п. 31 «е(2)», ПП РФ № 416, п. 36). У лифта, мусора, "
    "подъезда и двора срок 24 часа или 3 суток задал сервис\n\n"
    "🔴 Срок прошел, а УК молчит\n"
    "Я пришлю сообщение о просрочке. В карточке заявки в приложении попросите "
    "руководство УК вмешаться: заявка встанет у УК первой. Не помогло - там же "
    "готовая жалоба в ГЖИ, PDF придет в этот чат\n\n"
    "👎 Работу сделали плохо\n"
    "На приемке нажмите «👎 Сделано плохо», опишите и приложите фото - уйдет "
    "повторная заявка. Если проблема вернулась после закрытия, подайте новую\n\n"
    "↩️ Как отменить заявку?\n"
    "Кнопкой «↩️ Отменить заявку» после отправки или в приложении, пока работу "
    "не сдали на приемку. УК получит причину\n\n"
    "🚨 Что делать при аварии?\n"
    "Сначала позвоните: 112 при угрозе жизни, 104 при запахе газа, затем "
    "в аварийную службу дома - номер в «🚨 Авария». Потом подайте заявку\n\n"
    "🏠 Дом не подключен\n"
    "Его УК еще не работает в Жэке, и заявку передать некому. Нажмите «Мне нужен» "
    "на Главной в приложении - передадим спрос УК. Там же можно подготовить "
    "письмо в УК, если она известна\n\n"
    "🔑 Как подтвердить квартиру?\n"
    "В приложении: по лицевому счету или QR из квитанции, или запросом в УК. "
    "Арендатор входит по ссылке-приглашению собственника. Без подтверждения "
    "можно подавать заявки, а счетчики и начисления закрыты\n\n"
    "📟 Как передать показания?\n"
    "Фото счетчика без подписи сюда или в приложении, «Моя квартира». Нужны "
    "подтвержденная квартира и действующая поверка, счетчики заводит УК. Прием "
    "открыт в дни, которые задала УК\n\n"
    "🔔 Как настроить уведомления?\n"
    "В профиле приложения, «Уведомления и звук»: со звуком, без звука или "
    "выключены. Статусы ваших заявок, приемка работ, записи и запросы доступа "
    "приходят всегда, у них отключается только звук\n\n"
    "💬 Как подключить чат дома?\n"
    "Добавьте меня в группу MAX. Привязать ее к дому может сотрудник УК, "
    "председатель совета или житель с кодом привязки, затем меня нужно сделать "
    "администратором\n\n"
    "🗑 Как удалить мои данные?\n"
    "Командой /delete или в профиле приложения. Заявки, показания и голоса "
    "останутся историей дома без вашего имени\n\n"
    "💡 Все, что я умею, - в /help. Больше ответов - в приложении: профиль, "
    "«Помощь», «Как это работает»"
)
SEEDING_TEXT = "⏳ Заполняю демо-данные, это займет до минуты"
DEMO_REMINDERS_TEXT = "🧪 Так приходят напоминания по расписанию"
CHAT_COMMANDS_ONLY = (
    "💬 Команды /pin, /unpin и /repin работают только в чате дома, "
    "и пользоваться ими могут председатель и сотрудники УК"
)
BOT_COMMANDS = [
    BotCommand(name="start", description="Открыть меню"),
    BotCommand(name="help", description="Что умеет бот"),
    BotCommand(name="faq", description="Частые вопросы"),
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


@router.message_created(Command("faq"))
async def faq_handler(update: MessageCreated) -> None:
    await update.answer_text(FAQ_TEXT, notify=False)
