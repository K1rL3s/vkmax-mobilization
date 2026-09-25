from collections.abc import Mapping
from datetime import date, datetime
from html import escape

from zheka.core.enums import RequestStatus
from zheka.core.ids import RequestId

BLOCKED = "УК закрыла вам доступ к этому дому"

REQUEST_STATUS_LABELS: Mapping[RequestStatus, str] = {
    RequestStatus.NEW: "Новая",
    RequestStatus.ACCEPTED: "Принята",
    RequestStatus.IN_PROGRESS: "В работе",
    RequestStatus.ON_REVIEW: "На приемке",
    RequestStatus.DONE: "Выполнена",
}


def request_status_changed(
    request_id: RequestId,
    status: RequestStatus,
    comment: str | None,
) -> str:
    text = f"🔔 Заявка №{request_id}: {REQUEST_STATUS_LABELS[status]}"
    if comment:
        text = f"{text}\n\n{escape(comment)}"
    return text


def request_reply(request_id: RequestId, text: str) -> str:
    return f"💬 Ответ УК по заявке №{request_id}\n\n{escape(text)}"


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
    return "📟 Открыт прием показаний счетчиков. Передайте их в мини-приложении"


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
    return (
        f"🗳 Идет опрос «{escape(title)}», голосование закончится "
        f"{ends_at:%d.%m.%Y}. Проголосовать можно в мини-приложении"
    )


def verification_soon(meter: str, serial: str, due: date) -> str:
    return (
        f"⏰ {due:%d.%m.%Y} истекает поверка счетчика «{meter}» №{escape(serial)}. "
        "После этого начисление пойдет по нормативу"
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
        "📟 Управляющая организация напоминает: прием показаний открыт, а "
        "ваших еще нет. Передайте их в мини-приложении"
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
