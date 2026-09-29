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

from zheka.bot.cards import BACK, EMERGENCY, TO_MENU
from zheka.bot.handlers.fallback import on_free_text
from zheka.bot.handlers.requests.handlers import (
    SENT_TEXT,
    get_cancel,
    get_category,
    get_description,
    get_draft,
    get_sent,
    on_attachment,
    on_cancel_reason,
    on_category,
    on_description,
    on_description_attachment,
    on_description_voice,
    on_send,
    on_start,
)
from zheka.bot.states import Menu, NewRequest, Onboarding
from zheka.bot.voice import VOICE_FAILED, VOICE_PENDING
from zheka.core.texts import DANGER_REQUEST_NOTE, OPEN_REQUEST

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
WORKS_TEXT = (
    "🚧 По дому идут плановые работы до {works_until}. "
    "Если у вас другая проблема, опишите ее"
)
DESCRIPTION_ATTACHMENTS_TEXT = "📎 Вложений приложено: {attachments}"
ATTACHMENTS_TEXT = "📷 Пришлите фото или видео проблемы. Вложений: {attachments}"
CONFIRM_TEXT = (
    "📋 Проверьте заявку\n\n{category}\n\n{description}\n\nВложений: {attachments}"
)
CREATED_TEXT = (
    "✅ Заявка №{request_id} отправлена в УК\n"
    "{deadline}\n"
    "Сообщу, когда ее примут в работу"
)
CANCEL_TEXT = (
    "↩️ Почему отменяете заявку №{request_id}?\n"
    "Другую причину можно указать в приложении"
)

request_dialog = Dialog(
    Window(
        Multi(
            Multi(
                Format("{danger}"),
                Const(DANGER_REQUEST_NOTE, when=F["connected"]),
                when=F["danger"],
            ),
            Const(NO_HOUSE_TEXT, when=~F["address"]),
            Format(NOT_CONNECTED_TEXT, when=F["address"] & ~F["connected"]),
            Format(CATEGORY_TEXT, when=F["connected"] & ~F["description"]),
            Format(PROBLEM_TEXT, when=F["connected"] & F["description"]),
            sep="\n\n",
        ),
        Start(EMERGENCY, id="emergency", state=Menu.emergency),
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
            Const(VOICE_FAILED, when=F["voice_failed"]),
            Format(WORKS_TEXT, when=F["works_until"]),
            Const(DESCRIPTION_TEXT),
            Format(DESCRIPTION_ATTACHMENTS_TEXT, when=F["attachments"]),
            Format("🎬 Видео: {videos}", when=F["videos"]),
            Const(VOICE_PENDING, when=F["voice_pending"]),
            sep="\n\n",
        ),
        MessageInput(
            on_description_attachment,
            content_types=[AttachmentType.IMAGE, AttachmentType.VIDEO],
        ),
        MessageInput(on_description_voice, content_types=[AttachmentType.AUDIO]),
        TextInput(id="description", on_success=on_description),
        Row(SwitchTo(BACK, id="to_category", state=NewRequest.category), TO_MENU),
        state=NewRequest.description,
        getter=get_description,
    ),
    Window(
        Format("{error}", when=F["error"]),
        Format(ATTACHMENTS_TEXT),
        Format("🎬 Видео: {videos}", when=F["videos"]),
        MessageInput(
            on_attachment,
            content_types=[AttachmentType.IMAGE, AttachmentType.VIDEO],
        ),
        SwitchTo(Const("➡️ Дальше"), id="to_confirm", state=NewRequest.confirm),
        Row(SwitchTo(BACK, id="photo_back", state=NewRequest.description), TO_MENU),
        state=NewRequest.attachments,
        getter=get_draft,
    ),
    Window(
        Format(CONFIRM_TEXT),
        Format("🎬 Видео: {videos}", when=F["videos"]),
        Button(Const("📨 Отправить"), id="send", on_click=on_send),
        Row(SwitchTo(BACK, id="to_photo", state=NewRequest.attachments), TO_MENU),
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
        SwitchTo(
            Const("↩️ Отменить заявку"),
            id="cancel_request",
            state=NewRequest.cancel,
            when=F["request_id"],
        ),
        MessageInput(on_free_text),
        TO_MENU,
        state=NewRequest.sent,
        getter=get_sent,
    ),
    Window(
        Format(CANCEL_TEXT),
        Column(
            Select(
                Format("{item[label]}"),
                id="cancel_reason",
                item_id_getter=lambda reason: reason["id"],
                items="reasons",
                on_click=on_cancel_reason,
            ),
        ),
        Row(SwitchTo(BACK, id="cancel_back", state=NewRequest.sent), TO_MENU),
        state=NewRequest.cancel,
        getter=get_cancel,
    ),
    on_start=on_start,
)
