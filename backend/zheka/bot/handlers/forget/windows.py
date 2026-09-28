from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.kbd import Button
from maxo.dialogs.widgets.text import Const

from zheka.bot.handlers.forget.handlers import on_forget, on_keep
from zheka.bot.states import Forget

FORGET_TEXT = (
    "🗑 Удалить мои данные?\n\n"
    "❌ Удалятся имя, привязки к домам и квартирам, подтверждение квартиры, "
    "роли в УК, настройки уведомлений и согласие на обработку данных\n\n"
    "📂 Останутся без вашего имени заявки с фото и перепиской, показания "
    "счетчиков и голоса в опросах: это история дома и квартиры"
)

forget_dialog = Dialog(
    Window(
        Const(FORGET_TEXT),
        Button(Const("🗑 Удалить"), id="forget", on_click=on_forget),
        Button(Const("↩️ Отмена"), id="keep", on_click=on_keep),
        state=Forget.confirm,
    ),
)
