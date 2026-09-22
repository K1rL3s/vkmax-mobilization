import json

from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.kbd import Button, WebApp
from maxo.dialogs.widgets.text import Const, Format, Multi
from maxo.utils.payload import encode_payload

from zheka.bot.handlers.consent.handlers import get_consent, on_accept
from zheka.bot.states import Consent
from zheka.core.consent import CONSENT_TEXT

GIVEN_TEXT = "✅ Согласие дано"
POLICY_PAYLOAD = encode_payload(json.dumps({"path": "/privacy"}, separators=(",", ":")))

consent_dialog = Dialog(
    Window(
        Multi(Const(CONSENT_TEXT), Const(GIVEN_TEXT, when=F["given"]), sep="\n\n"),
        Button(
            Const("✅ Даю согласие"),
            id="accept",
            on_click=on_accept,
            when=~F["given"],
        ),
        WebApp(
            Const("📄 Политика обработки данных"),
            Format("{bot_username}"),
            payload=Const(POLICY_PAYLOAD),
            when=~F["given"] & F["bot_username"],
        ),
        state=Consent.ask,
        getter=get_consent,
    ),
)
