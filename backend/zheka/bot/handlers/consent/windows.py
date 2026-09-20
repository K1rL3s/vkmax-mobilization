from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.kbd import Button
from maxo.dialogs.widgets.text import Const

from zheka.bot.handlers.consent.handlers import on_accept
from zheka.bot.states import Consent
from zheka.core.consent import CONSENT_TEXT

# текст один на бота и на чекбокс мини-аппа: два разошедшихся согласия - это
# не удобство, а юридическая проблема
consent_dialog = Dialog(
    Window(
        Const(CONSENT_TEXT),
        Button(Const("Согласен"), id="accept", on_click=on_accept),
        state=Consent.ask,
    ),
)
