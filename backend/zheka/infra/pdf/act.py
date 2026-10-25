from datetime import datetime

from zheka.core.enums import RequestCompletionReason
from zheka.core.services.requests import UTILITY_SERVICES, RequestCardData
from zheka.infra.pdf.document import NOTE_GREY, PdfDocument
from zheka.infra.pdf.gji import CHANNELS, PRINTED, history_rows

BLANK = "_" * 82

GROUNDS = (
    "Основание: п. 110(1) Правил предоставления коммунальных услуг "
    "(постановление Правительства РФ от 06.05.2011 № 354): если исполнитель не "
    "провел проверку качества в срок по п. 108 Правил, потребитель вправе "
    "составить акт в его отсутствие; акт подписывают не менее 2 потребителей и "
    "председатель совета многоквартирного дома, а при управлении товариществом "
    "или кооперативом - его председатель. Дата и время начала нарушения из акта "
    "учитываются при перерасчете платы, если нарушение подтвердит проверка "
    "исполнителя или экспертиза (п. 111 «г» Правил)."
)

HOW_TO_USE = (
    "Составьте акт в двух экземплярах: один передайте в управляющую организацию "
    "с отметкой о приеме на втором, второй оставьте себе. Приложите фото замеров."
)


class NeighbourAct(PdfDocument):
    def __init__(self, card: RequestCardData, now: datetime) -> None:
        request = card.request
        demo = card.org is not None and card.org.is_demo
        note = (
            "Черновик подготовлен сервисом «Жэка Коммуналкин» по заявке "
            f"№{request.id} {card.house.local(now):{PRINTED}}. Впишите замеры "
            "и подпишите вместе с соседями"
        )
        if demo:
            note = f"{note}. ДЕМО: заявка в демонстрационной УК, не для подачи"
        super().__init__(f"Акт по заявке №{request.id}", note, demo=demo)
        self._card = card
        self.heading(
            "АКТ\nо непредоставлении (ненадлежащем качестве) коммунальной услуги",
        )
        self.paragraph(
            "Акт проверки качества, составленный потребителем в отсутствие "
            "исполнителя (п. 110(1) Правил, утв. постановлением Правительства РФ "
            "от 06.05.2011 № 354)",
            size=9,
            align="C",
        )
        self.paragraph(
            "Дата и время проверки и составления акта: «____» ____________ 20___ г. "
            "____ ч ____ мин",
        )
        self._facts()
        self._measurements()
        self.paragraph(GROUNDS)
        self._signatures()
        self.paragraph(f"Приложение: история заявки №{request.id}", bold=True)
        self.grid(
            ("Дата и время", "Статус", "Кто изменил"),
            history_rows(card),
            (40, 55, 75),
        )
        with self.local_context(text_color=NOTE_GREY):
            self.paragraph(HOW_TO_USE, size=8.5)

    def _moment(self, moment: datetime) -> str:
        return f"{self._card.house.local(moment):{PRINTED}}"

    def _facts(self) -> None:
        card = self._card
        request = card.request
        flat = "____" if card.flat is None else card.flat.number
        self.paragraph(f"Адрес: {card.house.address}, кв. {flat}")
        if card.org is not None:
            self.paragraph(
                f"Исполнитель: {card.org.name}, ИНН {card.org.inn}, "
                f"телефон: {card.org.phone}",
            )
        self.paragraph(
            f"Коммунальная услуга: {UTILITY_SERVICES[request.category]}",
            bold=True,
            align="L",
        )
        self.paragraph(
            "Нарушение (нужное подчеркнуть): услуга не предоставляется / "
            "предоставляется ненадлежащего качества / с перерывами сверх "
            "допустимой продолжительности",
        )
        self.paragraph(
            "Дата и время начала нарушения: "
            f"{self._moment(request.created_at)} - подача заявки №{request.id} в "
            f"управляющую организацию {CHANNELS[request.channel]}. Суть заявки: "
            f"«{request.description}».",
        )
        moment = self._moment(request.done_at or request.created_at)
        if request.completion_reason is RequestCompletionReason.RESIDENT_REJECTED:
            self.paragraph(
                f"{moment} потребитель не принял работу по заявке: нарушение не "
                "устранено.",
            )
        elif request.completion_reason is RequestCompletionReason.AUTO_CLOSED:
            self.paragraph(
                f"{moment} заявку закрыли без приемки потребителем, затем "
                "потребитель сообщил, что нарушение не устранено, и подал "
                "повторную заявку.",
            )
        else:
            self.paragraph(
                f"Срок выполнения заявки истек {self._moment(request.deadline_at)}, "
                "нарушение не устранено.",
            )
        self.paragraph(
            "Исполнитель не провел проверку качества в срок по п. 108 Правил / "
            "сообщить ему о нарушении не удалось из-за ненадлежащей работы "
            "аварийной службы (нужное подчеркнуть).",
        )

    def _measurements(self) -> None:
        self.paragraph(
            "Выявленные нарушения параметров качества (температура воздуха в "
            "помещении, температура или давление воды, напряжение и т. п.), чем и "
            "как измерено:",
        )
        self.paragraph(f"{BLANK}\n{BLANK}\n{BLANK}", align="L")

    def _signatures(self) -> None:
        self.paragraph("Подписи", bold=True)
        self.grid(
            ("Кто подписывает", "Фамилия, имя, отчество", "Кв.", "Подпись"),
            [
                ("Потребитель, составивший акт", "", "", ""),
                ("Потребитель (сосед)", "", "", ""),
                ("Потребитель (сосед)", "", "", ""),
                ("Председатель совета дома", "", "", ""),
            ],
            (58, 62, 15, 35),
            line_height=8,
        )
