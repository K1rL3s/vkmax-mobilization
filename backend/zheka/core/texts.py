from collections.abc import Mapping
from datetime import date, datetime, timedelta
from html import escape
from math import ceil

from zheka.core.enums import CATEGORY_RULES, RequestCategory, RequestStatus
from zheka.core.ids import RequestId
from zheka.core.models import House, Request

BLOCKED = "УК закрыла вам доступ к этому дому"
OPEN_REQUEST = "📱 Открыть заявку"
SUBMIT_READINGS = "📟 Передать показания"
MY_METERS = "📟 Мои счетчики"
VOTE = "🗳 Проголосовать"
MY_APPOINTMENTS = "📅 Мои записи"
CABINET_BUTTON = "🧑‍💼 Открыть кабинет УК"
MOMENT = "%H:%M %d.%m"
NO_NORM = "Срок сервиса, норматива нет"

REQUEST_STATUS_LABELS: Mapping[RequestStatus, str] = {
    RequestStatus.NEW: "Новая",
    RequestStatus.ACCEPTED: "Принята",
    RequestStatus.IN_PROGRESS: "В работе",
    RequestStatus.ON_REVIEW: "На приемке",
    RequestStatus.DONE: "Выполнена",
}


REQUEST_STATUS_NEWS: Mapping[RequestStatus, str] = {
    RequestStatus.NEW: "новая",
    RequestStatus.ACCEPTED: "принята в работу",
    RequestStatus.IN_PROGRESS: "исполнитель приступил к работе",
    RequestStatus.ON_REVIEW: "работа выполнена, проверьте ее",
    RequestStatus.DONE: "выполнена",
}


def request_status_changed(
    request: Request,
    house: House,
    comment: str | None,
) -> str:
    text = (
        f"🔔 Заявка {_request(request.id, request.category)}: "
        f"{REQUEST_STATUS_NEWS[request.status]}"
    )
    if request.status is not RequestStatus.DONE:
        text = f"{text}\n{deadline_lines(request, house)}"
    if comment:
        text = f"{text}\n\n{escape(comment)}"
    return text


def request_reply(request_id: RequestId, category: RequestCategory, text: str) -> str:
    head = f"💬 Ответ УК по заявке {_request(request_id, category)}\n\n"
    tail = "\n\n↩️ Ответить можно в приложении"
    return f"{head}{_fitted(text, head + tail)}{tail}"


def flat_verified(flat_number: str, address: str) -> str:
    return f"✅ УК подтвердила вашу квартиру {escape(flat_number)}, {escape(address)}"


def flat_verification_rejected(flat_number: str, address: str, reason: str) -> str:
    return (
        f"❌ УК отклонила подтверждение квартиры {escape(flat_number)}, "
        f"{escape(address)}\n\nПричина: {escape(reason)}"
    )


def resident_blocked(address: str, reason: str, contact: str) -> str:
    return (
        f"⛔ УК закрыла вам доступ к дому {escape(address)}\n\n"
        f"Причина: {escape(reason)}\n\n{contact}"
    )


def resident_unblocked(address: str) -> str:
    return f"✅ УК вернула вам доступ к дому {escape(address)}"


def announcement(org_name: str, text: str, *, urgent: bool) -> str:
    heading = "🚨 Срочное объявление" if urgent else "📢 Объявление"
    return f"{heading} от {escape(org_name)}\n\n{escape(text)}"


def blocked_detail(reason: str | None) -> str:
    return BLOCKED if reason is None else f"{BLOCKED}: {reason}"


def request_auto_closed(request_id: RequestId) -> str:
    return (
        f"🔒 Заявка №{request_id} закрыта: работу не проверили за 48 часов. "
        "Если проблема осталась, подайте повторную заявку"
    )


def reading_window_opened() -> str:
    return "📟 Открыт прием показаний счетчиков"


def reading_window_closing(days: int) -> str:
    return (
        f"⏰ Через {_days(days)} закрывается прием показаний, а ваших еще нет. "
        "Без них начисление пойдет по нормативу"
    )


def poll_reminder(title: str, ends_at: datetime) -> str:
    return (
        f"🗳 Идет опрос «{escape(title)}», голосование закончится "
        f"{ends_at:%d.%m.%Y}. От вашей квартиры голоса еще нет"
    )


def poll_chat_reminder(title: str, ends_at: datetime) -> str:
    return f"🗳 Идет опрос «{escape(title)}», голосование закончится {ends_at:%d.%m.%Y}"


def verification_soon(meter: str, serial: str, due: date, days: int) -> str:
    return (
        f"⏰ Через {_days(days)}, {due:%d.%m.%Y}, истекает поверка счетчика "
        f"«{meter}» №{escape(serial)}. После этого начисление пойдет по нормативу"
    )


def verification_expired(meter: str, serial: str) -> str:
    return (
        f"⚠️ Истекла поверка счетчика «{meter}» №{escape(serial)}: начисление "
        "пойдет по нормативу, пока счетчик не поверят"
    )


def appointment_reminder(starts_at: datetime, address: str) -> str:
    return (
        f"📅 Напоминаем: завтра в {starts_at:%H:%M} вы записаны на прием в УК "
        f"по дому {escape(address)}"
    )


def _days(count: int) -> str:
    teen, units = count % 100 // 10 == 1, count % 10
    if not teen and units == 1:
        return f"{count} день"
    if not teen and units in {2, 3, 4}:
        return f"{count} дня"
    return f"{count} дней"


def reading_reminder_manual() -> str:
    return (
        "📟 Управляющая организация напоминает: прием показаний открыт, а ваших еще нет"
    )


REQUEST_EXPORT_DISCLAIMER = (
    "Документ сформирован автоматически и юридической силы не имеет."
)


def org_contact(name: str, phone: str) -> str:
    contact = escape(name)
    if phone.strip():
        contact = f"{contact}, {escape(phone)}"
    return f"Связаться с УК: {contact}"


def flat_verification_revoked(address: str, reason: str, contact: str) -> str:
    return (
        f"⚠️ УК отозвала подтверждение вашей квартиры в доме {escape(address)}\n\n"
        f"Причина: {escape(reason)}\n\n{contact}"
    )


def request_created(request: Request, house: House) -> str:
    return (
        f"🆕 Заявка {_request(request.id, request.category)}\n"
        f"🏢 {escape(house.address)}\n{deadline_lines(request, house)}"
    )


def _request(request_id: RequestId, category: RequestCategory) -> str:
    return f"№{request_id} «{CATEGORY_RULES[category].caption}»"


def verification_today(meter: str, serial: str) -> str:
    return (
        f"⏰ Сегодня последний день поверки счетчика «{meter}» №{escape(serial)}. "
        "С завтрашнего дня начисление пойдет по нормативу"
    )


def deadline_lines(request: Request, house: House) -> str:
    lines = [
        f"⏰ Срок: до {house.local(request.deadline_at):{MOMENT}}",
        f"📜 {CATEGORY_RULES[request.category].basis or NO_NORM}",
    ]
    if request.status is RequestStatus.NEW and request.react_deadline_at is not None:
        lines.insert(
            0,
            f"⏱ Принять до {house.local(request.react_deadline_at):{MOMENT}}",
        )
    return "\n".join(lines)


COMPLAINT_BUTTON = "📄 Жалоба в ГЖИ"


def deadline_warning(request: Request, house: House, now: datetime) -> str:
    hours = ceil((request.deadline_at - now) / timedelta(hours=1))
    return (
        f"⏳ Заявке {_request(request.id, request.category)} осталось {hours} ч\n"
        f"⏰ Срок: до {house.local(request.deadline_at):{MOMENT}}"
    )


def request_overdue_staff(request: Request, house: House) -> str:
    return (
        f"🔴 Заявка {_request(request.id, request.category)} просрочена\n"
        f"🏢 {escape(house.address)}"
    )


def request_overdue_author(request: Request) -> str:
    return (
        f"🔴 Срок по заявке {_request(request.id, request.category)} истек\n"
        f"📜 {CATEGORY_RULES[request.category].basis or NO_NORM}\n"
        "📄 Можно подготовить жалобу в ГЖИ"
    )


def request_overdue_chairman(request: Request) -> str:
    return f"🔴 В доме просрочена заявка {_request(request.id, request.category)}"


def executor_declined(
    request_id: RequestId,
    category: RequestCategory,
    executor: str,
    reason: str,
) -> str:
    head = (
        f"🙅 {escape(executor)} отказался от заявки {_request(request_id, category)}"
        "\n💬 "
    )
    return f"{head}{_fitted(reason, head)}"


MESSAGE_LIMIT = 4000


def _units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _fitted(quote: str, frame: str) -> str:
    room = MESSAGE_LIMIT - _units(frame)
    escaped = escape(quote)
    if _units(escaped) <= room:
        return escaped
    kept: list[str] = []
    size = _units("…")
    for char in quote:
        part = escape(char)
        size += _units(part)
        if size > room:
            break
        kept.append(part)
    return f"{''.join(kept)}…"


def request_escalated(request: Request, house: House, now: datetime) -> str:
    hours = max(1, ceil((now - request.deadline_at) / timedelta(hours=1)))
    return (
        "⬆️ Житель просит руководство вмешаться: заявка "
        f"{_request(request.id, request.category)} просрочена на {hours} ч\n"
        f"🏢 {escape(house.address)}"
    )


def request_escalated_author(request: Request) -> str:
    return (
        "⬆️ Руководство УК уведомлено о просрочке заявки "
        f"{_request(request.id, request.category)}\n"
        "📄 Если ничего не изменится, можно подать жалобу в ГЖИ"
    )
