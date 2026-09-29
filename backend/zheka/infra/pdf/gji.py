from collections.abc import Mapping
from datetime import datetime, timedelta
from math import ceil

from zheka.core.enums import CATEGORY_RULES, RequestActorRole, RequestChannel
from zheka.core.services.requests import RequestCardData
from zheka.core.texts import REQUEST_STATUS_LABELS
from zheka.infra.pdf.document import NOTE_GREY, PdfDocument

SIGNATURE_ROWS = 5
PRINTED = "%d.%m.%Y %H:%M"

ACTORS: Mapping[str, str] = {
    RequestActorRole.RESIDENT: "житель",
    RequestActorRole.STAFF: "управляющая организация",
    RequestActorRole.EXECUTOR: "исполнитель УК",
    RequestActorRole.SYSTEM: "сервис",
}

CHANNELS: Mapping[RequestChannel, str] = {
    RequestChannel.MINIAPP: (
        "через мини-приложение «Жэка Коммуналкин» в мессенджере MAX"
    ),
    RequestChannel.BOT: "через бота «Жэка Коммуналкин» в мессенджере MAX",
    RequestChannel.CHAT: "через домовой чат в мессенджере MAX",
    RequestChannel.PHONE: "по телефону",
}

GROUNDS = (
    "Управляющая организация отвечает перед собственниками помещений за "
    "оказание услуг и выполнение работ, которые обеспечивают надлежащее "
    "содержание общего имущества в доме (ч. 2.3 ст. 161 Жилищного кодекса РФ). "
    "Порядок приема и исполнения заявок установлен Правилами осуществления "
    "деятельности по управлению многоквартирными домами (постановление "
    "Правительства РФ от 15.05.2013 № 416). Соблюдение этих требований "
    "проверяет государственный жилищный надзор (ст. 20 Жилищного кодекса РФ)."
)

WHERE_TO_FILE = (
    "Куда подать: лично или почтой в жилищную инспекцию региона, через "
    "электронную приемную на ее сайте, через ГИС ЖКХ (dom.gosuslugi.ru) или "
    "платформу «Госуслуги. Решаем вместе» (pos.gosuslugi.ru)."
)


class GjiComplaint(PdfDocument):
    def __init__(self, card: RequestCardData, now: datetime) -> None:
        request = card.request
        demo = card.org is not None and card.org.is_demo
        note = (
            "Черновик подготовлен сервисом «Жэка Коммуналкин» по заявке "
            f"№{request.id} {card.house.local(now):{PRINTED}}. Проверьте текст, "
            "впишите свои данные и подпишите"
        )
        if demo:
            note = f"{note}. ДЕМО: заявка в демонстрационной УК, не для подачи"
        super().__init__(f"Жалоба по заявке №{request.id}", note, demo=demo)
        self._card = card
        self._now = now
        self._addressee()
        self.heading(
            "ЖАЛОБА\nна нарушение управляющей организацией срока выполнения заявки",
        )
        self._facts()
        self.paragraph(GROUNDS)
        self._history()
        self._requests()
        self._signatures()
        with self.local_context(text_color=NOTE_GREY):
            self.paragraph(WHERE_TO_FILE, size=8.5)

    def _moment(self, moment: datetime) -> str:
        return f"{self._card.house.local(moment):{PRINTED}}"

    def _addressee(self) -> None:
        left = self.l_margin
        self.set_left_margin(self.w / 2)
        self.set_x(self.w / 2)
        self.paragraph(
            "В государственную жилищную инспекцию\n"
            f"{self._card.house.region}\n\n"
            "от: ______________________________\n"
            "(фамилия, имя, отчество)\n"
            "адрес для ответа: ________________\n"
            "__________________________________\n"
            "телефон или e-mail: ______________",
            size=9.5,
            align="L",
        )
        self.set_left_margin(left)
        self.ln(4)

    def _facts(self) -> None:
        card = self._card
        request = card.request
        rule = CATEGORY_RULES[request.category]
        flat = "" if card.flat is None else f", кв. {card.flat.number}"
        self.paragraph(
            f"{self._moment(request.created_at)} {CHANNELS[request.channel]} я "
            f"подал(а) в управляющую организацию заявку №{request.id} по категории "
            f"«{rule.label}». Адрес: "
            f"{card.house.address}{flat}. Суть заявки: «{request.description}».",
        )
        if card.org is not None:
            org = card.org
            license_no = (
                "" if org.license_no is None else f", лицензия № {org.license_no}"
            )
            self.paragraph(
                f"Управляющая организация: {org.name}, ИНН {org.inn}{license_no}, "
                f"адрес: {org.address}, телефон: {org.phone}.",
            )
        deadline = self._moment(request.deadline_at)
        self.paragraph(
            f"Срок выполнения заявки этой категории - {rule.deadline_text} с "
            f"подачи, он истек {deadline}. Срок основан на норме: {rule.basis}."
            if rule.basis
            else f"Срок выполнения заявки этой категории, который сервис назначил "
            f"при подаче, - {rule.deadline_text}, он истек {deadline}.",
        )
        hours = max(1, ceil((self._now - request.deadline_at) / timedelta(hours=1)))
        days, rest = divmod(hours, 24)
        overdue = f"{hours} ч" if days == 0 else f"{days} сут. {rest} ч"
        self.paragraph(
            f"На {self._moment(self._now)} срок истек {overdue} назад, работы не "
            "завершены. Статус заявки: "
            f"«{REQUEST_STATUS_LABELS[request.status]}».",
            bold=True,
        )
        if request.escalated_at is not None:
            self.paragraph(
                f"{self._moment(request.escalated_at)} я попросил(а) руководство "
                "управляющей организации вмешаться, нарушение не устранено.",
            )
        if rule.pp290_refs:
            self.paragraph(
                "Работы по заявке входят в минимальный перечень услуг и работ, "
                "необходимых для надлежащего содержания общего имущества "
                "(постановление Правительства РФ от 03.04.2013 № 290, "
                f"{', '.join(rule.pp290_refs)}).",
            )
        if card.group_size > 1:
            self.paragraph(
                "Обращений жителей дома с той же проблемой, объединенных в общую "
                f"заявку: {card.group_size}.",
            )

    def _history(self) -> None:
        self.paragraph("История заявки", bold=True)
        self.grid(
            ("Дата и время", "Статус", "Кто изменил"),
            [
                (
                    self._moment(log.at),
                    REQUEST_STATUS_LABELS[log.to_status],
                    ACTORS.get(log.by_role, log.by_role),
                )
                for log in self._card.timeline
            ],
            (40, 55, 75),
        )

    def _requests(self) -> None:
        self.paragraph("Прошу:", bold=True)
        self.paragraph(
            "1. Провести проверку исполнения управляющей организацией обязанностей "
            f"по заявке №{self._card.request.id}.\n"
            "2. Обязать управляющую организацию устранить нарушение.\n"
            "3. Сообщить мне о результатах рассмотрения в срок, установленный "
            "ст. 12 Федерального закона от 02.05.2006 № 59-ФЗ «О порядке "
            "рассмотрения обращений граждан Российской Федерации».",
        )
        self.ln(4)
        self.paragraph(
            "Дата: «____» ______________ 20___ г.          Подпись: ______________",
        )
        self.ln(4)

    def _signatures(self) -> None:
        self.paragraph("Жалобу поддерживают соседи", bold=True)
        self.grid(
            ("№", "Фамилия, имя, отчество", "Кв.", "Подпись"),
            [
                (str(number), "", "", "")
                for number in range(
                    1,
                    max(self._card.group_size, SIGNATURE_ROWS) + 1,
                )
            ],
            (10, 90, 20, 50),
            line_height=7,
        )
