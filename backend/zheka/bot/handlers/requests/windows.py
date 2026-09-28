from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import MessageInput, TextInput
from maxo.dialogs.widgets.kbd import (
    Button,
    Column,
    Row,
    Select,
    Start,
    SwitchTo,
    WebApp,
)
from maxo.dialogs.widgets.text import Const, Format, Multi
from maxo.enums import AttachmentType

from zheka.bot.cards import BACK, TO_MENU
from zheka.bot.handlers.fallback import on_free_text
from zheka.bot.handlers.requests.handlers import (
    SENT_TEXT,
    get_category,
    get_draft,
    get_sent,
    on_category,
    on_description,
    on_description_photo,
    on_photo,
    on_send,
    on_start,
)
from zheka.bot.states import NewRequest, Onboarding
from zheka.core.texts import OPEN_REQUEST

NO_HOUSE_TEXT = "🏠 Сначала найдите свой дом, тогда будет кому передать заявку"
CATEGORY_TEXT = "🏢 {address}\n\n🛠 Что случилось?"
PROBLEM_TEXT = (
    "🏢 {address}\n\n📝 Создать заявку по проблеме «{description}»?\n\n"
    "🛠 Выберите, что случилось"
)
NOT_CONNECTED_TEXT = (
    "🏢 {address}\n\n😔 Управляющая компания этого дома еще не подключена к "
    "Жэке, заявку передать некому. Нажмите «Мне нужен» на главной в "
    "приложении - так УК узнает, что сервис здесь ждут"
)
DESCRIPTION_TEXT = "✍️ Опишите проблему одним сообщением"
DESCRIPTION_PHOTOS_TEXT = "📷 Фото приложено: {photos}"
PHOTO_TEXT = "📷 Пришлите фото, если есть. Приложено: {photos}"
CONFIRM_TEXT = "📋 Проверьте заявку\n\n{category}\n\n{description}\n\nФото: {photos}"
CREATED_TEXT = (
    "✅ Заявка №{request_id} отправлена в УК\n"
    "{deadline}\n"
    "Сообщу, когда ее примут в работу"
)

request_dialog = Dialog(
    Window(
        Const(NO_HOUSE_TEXT, when=~F["address"]),
        Format(NOT_CONNECTED_TEXT, when=F["address"] & ~F["connected"]),
        Format(CATEGORY_TEXT, when=F["connected"] & ~F["description"]),
        Format(PROBLEM_TEXT, when=F["connected"] & F["description"]),
        Column(
            Select(
                Format("{item[label]}"),
                id="category",
                item_id_getter=lambda category: category["id"],
                items="categories",
                on_click=on_category,
            ),
        ),
        MessageInput(on_free_text),
        Start(
            Const("🔎 Найти дом"),
            id="find_house",
            state=Onboarding.method,
            when=~F["address"],
        ),
        TO_MENU,
        state=NewRequest.category,
        getter=get_category,
    ),
    Window(
        Multi(
            Const(DESCRIPTION_TEXT),
            Format(DESCRIPTION_PHOTOS_TEXT, when=F["photos"]),
            sep="\n\n",
        ),
        MessageInput(on_description_photo, content_types=[AttachmentType.IMAGE]),
        TextInput(id="description", on_success=on_description),
        Row(SwitchTo(BACK, id="to_category", state=NewRequest.category), TO_MENU),
        state=NewRequest.description,
        getter=get_draft,
    ),
    Window(
        Format(PHOTO_TEXT),
        MessageInput(on_photo, content_types=[AttachmentType.IMAGE]),
        SwitchTo(Const("➡️ Дальше"), id="to_confirm", state=NewRequest.confirm),
        Row(SwitchTo(BACK, id="photo_back", state=NewRequest.description), TO_MENU),
        state=NewRequest.photo,
        getter=get_draft,
    ),
    Window(
        Format(CONFIRM_TEXT),
        Button(Const("📨 Отправить"), id="send", on_click=on_send),
        Row(SwitchTo(BACK, id="to_photo", state=NewRequest.photo), TO_MENU),
        state=NewRequest.confirm,
        getter=get_draft,
    ),
    Window(
        Multi(
            Const(SENT_TEXT, when=~F["request_id"] & ~F["error"]),
            Format(CREATED_TEXT, when=F["request_id"]),
            Format("{error}", when=F["error"]),
        ),
        WebApp(
            Const(OPEN_REQUEST),
            Format("{bot_username}"),
            payload=Format("{request_payload}"),
            when=F["request_payload"] & F["bot_username"],
        ),
        MessageInput(on_free_text),
        TO_MENU,
        state=NewRequest.sent,
        getter=get_sent,
    ),
    on_start=on_start,
)
