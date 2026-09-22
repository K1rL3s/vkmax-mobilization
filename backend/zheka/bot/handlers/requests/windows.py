from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import MessageInput, TextInput
from maxo.dialogs.widgets.kbd import (
    Button,
    Cancel,
    ScrollingGroup,
    Select,
    Start,
    SwitchTo,
)
from maxo.dialogs.widgets.text import Const, Format, Multi
from maxo.enums import AttachmentType

from zheka.bot.cards import TO_MENU
from zheka.bot.handlers.requests.handlers import (
    SENT_TEXT,
    get_category,
    get_draft,
    get_sent,
    on_category,
    on_description,
    on_photo,
    on_send,
)
from zheka.bot.states import NewRequest, Onboarding

PAGE = 6

NO_HOUSE_TEXT = "🏠 Сначала найдите свой дом, тогда будет кому передать заявку"
CATEGORY_TEXT = "🏢 {address}\n\n🛠 Что случилось?"
NOT_CONNECTED_TEXT = (
    "🏢 {address}\n\n😔 Управляющая компания этого дома еще не подключена к "
    "Жэке, заявку передать некому. Нажмите «Мне нужен» в карточке дома в "
    "приложении - так УК узнает, что сервис здесь ждут"
)
DESCRIPTION_TEXT = "✍️ Опишите проблему одним сообщением"
PHOTO_TEXT = "📷 Пришлите фото, если есть. Приложено: {photos}"
CONFIRM_TEXT = "📋 Проверьте заявку\n\n{category}\n\n{description}\n\nФото: {photos}"
CREATED_TEXT = "✅ Заявка №{request_id} принята"

request_dialog = Dialog(
    Window(
        Const(NO_HOUSE_TEXT, when=~F["address"]),
        Format(NOT_CONNECTED_TEXT, when=F["address"] & ~F["connected"]),
        Format(CATEGORY_TEXT, when=F["connected"]),
        ScrollingGroup(
            Select(
                Format("{item[label]}"),
                id="category",
                item_id_getter=lambda category: category["id"],
                items="categories",
                on_click=on_category,
            ),
            id="categories_scroll",
            width=1,
            height=PAGE,
        ),
        Start(
            Const("🔎 Найти дом"),
            id="find_house",
            state=Onboarding.method,
            when=~F["address"],
        ),
        Cancel(Const("❌ Отмена")),
        state=NewRequest.category,
        getter=get_category,
    ),
    Window(
        Const(DESCRIPTION_TEXT),
        TextInput(id="description", on_success=on_description),
        SwitchTo(Const("⬅️ Назад"), id="to_category", state=NewRequest.category),
        state=NewRequest.description,
    ),
    Window(
        Format(PHOTO_TEXT),
        MessageInput(on_photo, content_types=[AttachmentType.IMAGE]),
        SwitchTo(Const("➡️ Дальше"), id="to_confirm", state=NewRequest.confirm),
        state=NewRequest.photo,
        getter=get_draft,
    ),
    Window(
        Format(CONFIRM_TEXT),
        Button(Const("📨 Отправить"), id="send", on_click=on_send),
        SwitchTo(Const("📷 Изменить фото"), id="to_photo", state=NewRequest.photo),
        state=NewRequest.confirm,
        getter=get_draft,
    ),
    Window(
        Multi(
            Const(SENT_TEXT, when=~F["request_id"]),
            Format(CREATED_TEXT, when=F["request_id"]),
        ),
        TO_MENU,
        state=NewRequest.sent,
        getter=get_sent,
    ),
)
