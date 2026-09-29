from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

from zheka.core.enums import AnnouncementChannel, NoticeStatus, ResidentRole
from zheka.core.models import NoticeDelivery
from zheka.core.services.announcements import NoticeRegisterData, RegisterFlat
from zheka.infra.pdf.document import NOTE_GREY, PdfDocument

PRINTED = "%d.%m.%Y %H:%M"
SENDING_WINDOW = timedelta(minutes=10)
NOT_IN_SERVICE = "Нет в сервисе"

STATUSES: Mapping[NoticeStatus, str] = {
    NoticeStatus.DELIVERED: "Доставлено",
    NoticeStatus.FAILED: "MAX не доставил",
    NoticeStatus.MUTED: "Выключил объявления",
    NoticeStatus.BOT_STOPPED: "Бот остановлен",
}

ROLES: Mapping[ResidentRole, str] = {
    ResidentRole.OWNER: "собственник",
    ResidentRole.TENANT: "арендатор",
}

VERIFIED: Mapping[bool, str] = {True: "подтвержден", False: "не подтвержден"}

CAPTION = (
    "Реестр фиксирует доставку сообщения в MAX, прочтение MAX не сообщает. "
    "Квартиры без отметки нужно уведомить другим способом. Для собрания "
    "собственников реестр не заменяет заказное письмо."
)


class NoticeRegisterPdf(PdfDocument):
    def __init__(
        self,
        register: NoticeRegisterData,
        *,
        demo: bool,
        unmarked_only: bool,
    ) -> None:
        announcement = register.announcement.announcement
        generated = register.house.local(register.generated_at)
        note = (
            f"Реестр по объявлению №{announcement.id} сформирован сервисом "
            f"«Жэка Коммуналкин» {generated:{PRINTED}}"
        )
        if demo:
            note = f"{note}. ДЕМО: объявление демонстрационной УК"
        super().__init__(
            f"Реестр уведомлений по объявлению №{announcement.id}",
            note,
            demo=demo,
        )
        self._register = register
        self._sending = (
            announcement.delivered_count is None
            and register.generated_at - announcement.created_at < SENDING_WINDOW
        )
        self.heading("РЕЕСТР УВЕДОМЛЕНИЙ\nо доставке объявления в личные сообщения MAX")
        org = register.announcement.org_name
        self.paragraph(
            f"Дом: {register.house.address}" + ("" if org is None else f"\nУК: {org}"),
            align="L",
        )
        self.paragraph(
            f"Объявление от {self._at(announcement.created_at)}: «{announcement.text}»",
        )
        self._totals()
        flats = [
            flat for flat in register.flats if not (unmarked_only and flat.delivered)
        ]
        if unmarked_only:
            self.paragraph("Показаны только квартиры без отметки")
        if flats:
            self.grid(
                ("Кв.", "Подъезд", "Житель", "Статус", "Время"),
                [row for flat in flats for row in self._rows(flat)],
                (12, 20, 60, 42, 36),
            )
        else:
            self.paragraph(
                "Сообщение дошло до всех квартир"
                if register.flats
                else "В справочнике нет квартир этого дома",
            )
        with self.local_context(text_color=NOTE_GREY):
            self.paragraph(CAPTION, size=8.5)

    def _at(self, moment: datetime | None) -> str:
        if moment is None:
            return "-"
        return f"{self._register.house.local(moment):{PRINTED}}"

    def _totals(self) -> None:
        register = self._register
        total = len(register.flats)
        self.paragraph(
            f"Доставлено квартирам {register.flats_delivered} из {total}, "
            f"без отметки {total - register.flats_delivered}",
            bold=True,
        )
        self.paragraph(self._chat())
        flatless = register.without_flat
        if flatless:
            delivered = sum(row.status is NoticeStatus.DELIVERED for row in flatless)
            self.paragraph(
                f"Жители без квартиры: доставлено {delivered} из {len(flatless)}",
            )

    def _chat(self) -> str:
        announcement = self._register.announcement.announcement
        sent = announcement.delivered_chat
        if AnnouncementChannel.CHAT not in announcement.channels:
            return "В чат дома не отправлялось"
        if sent is None:
            return f"В чат дома: {'отправляется…' if self._sending else 'нет данных'}"
        if len(announcement.house_ids) > 1:
            return f"В чаты домов: отправлено в {sent}"
        return f"В чат дома: {'отправлено' if sent > 0 else 'не отправлено'}"

    def _rows(self, item: RegisterFlat) -> Sequence[Sequence[str]]:
        number = item.flat.number
        entrance = "-" if item.flat.entrance is None else str(item.flat.entrance)
        if not item.deliveries:
            return [(number, entrance, "-", NOT_IN_SERVICE, "-")]
        return [
            (
                number if index == 0 else "",
                entrance if index == 0 else "",
                "автор объявления"
                if row.role is None
                else f"{ROLES[row.role]}, {VERIFIED[row.verified]}",
                self._status(row),
                self._at(row.at),
            )
            for index, row in enumerate(item.deliveries)
        ]

    def _status(self, row: NoticeDelivery) -> str:
        if row.status is not NoticeStatus.PENDING:
            return STATUSES[row.status]
        return "Отправляется…" if self._sending else "Нет данных"
