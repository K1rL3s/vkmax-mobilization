from collections.abc import Mapping
from datetime import date, datetime
from html import escape
from types import MappingProxyType

from zheka.core.enums import RequestStatus
from zheka.core.ids import RequestId

BLOCKED = "УК закрыла вам доступ к этому дому"

REQUEST_STATUS_LABELS: Mapping[RequestStatus, str] = MappingProxyType(
    {
        RequestStatus.NEW: "Новая",
        RequestStatus.ACCEPTED: "Принята",
        RequestStatus.IN_PROGRESS: "В работе",
        RequestStatus.ON_REVIEW: "На приемке",
        RequestStatus.DONE: "Выполнена",
    },
)


def _plain(value: str) -> str:
    # бот отправляет сообщения в режиме HTML, а сюда приходит текст УК и
    # жителя: незакрытый угловой скобкой фрагмент иначе роняет отправку
    return escape(value)


def request_status_changed(
    request_id: RequestId,
    status: RequestStatus,
    comment: str | None,
) -> str:
    text = f"Заявка №{request_id}: {REQUEST_STATUS_LABELS[status]}"
    if comment:
        text = f"{text}\n\n{_plain(comment)}"
    return text


def request_reply(request_id: RequestId, text: str) -> str:
    return f"Ответ УК по заявке №{request_id}\n\n{_plain(text)}"


def flat_verified(flat_number: str, address: str) -> str:
    return f"УК подтвердила вашу квартиру {_plain(flat_number)}, {_plain(address)}"


def flat_verification_rejected(flat_number: str, address: str, reason: str) -> str:
    return (
        f"УК отклонила подтверждение квартиры {_plain(flat_number)}, "
        f"{_plain(address)}\n\nПричина: {_plain(reason)}"
    )


def resident_blocked(address: str, reason: str) -> str:
    return (
        f"УК закрыла вам доступ к дому {_plain(address)}\n\nПричина: {_plain(reason)}"
    )


def resident_unblocked(address: str) -> str:
    return f"УК вернула вам доступ к дому {_plain(address)}"


def announcement(org_name: str, text: str) -> str:
    return f"Объявление от {_plain(org_name)}\n\n{_plain(text)}"


def blocked_detail(reason: str | None) -> str:
    # причина из residents.block_reason: отказ без нее не подсказывает жителю,
    # к кому идти и что исправлять. Единственная строка файла без _plain:
    # она уезжает в detail ответа API, а не в сообщение MAX, - для бота
    # берите resident_blocked, иначе «<» от УК уедет в HTML неэкранированным
    return BLOCKED if reason is None else f"{BLOCKED}: {reason}"


def request_auto_closed(request_id: RequestId) -> str:
    return (
        f"Заявка №{request_id} закрыта: работу не проверили за 48 часов. "
        "Если проблема осталась, подайте повторную заявку"
    )


def reading_window_opened() -> str:
    return "Открыт прием показаний счетчиков. Передайте их в мини-приложении"


def reading_window_closing(days: int) -> str:
    return (
        f"Через {_days(days)} закрывается прием показаний, а ваших еще нет. "
        "Без них начисление пойдет по нормативу"
    )


def poll_reminder(title: str, ends_at: datetime) -> str:
    return (
        f"Идет опрос «{_plain(title)}», голосование закончится "
        f"{ends_at:%d.%m.%Y}. От вашей квартиры голоса еще нет"
    )


def poll_chat_reminder(title: str, ends_at: datetime) -> str:
    return (
        f"Идет опрос «{_plain(title)}», голосование закончится "
        f"{ends_at:%d.%m.%Y}. Проголосовать можно в мини-приложении"
    )


def verification_soon(meter: str, serial: str, due: date) -> str:
    return (
        f"{due:%d.%m.%Y} истекает поверка счетчика «{meter}» №{_plain(serial)}. "
        "После этого начисление пойдет по нормативу"
    )


def verification_expired(meter: str, serial: str) -> str:
    return (
        f"Истекла поверка счетчика «{meter}» №{_plain(serial)}: начисление "
        "пойдет по нормативу, пока счетчик не поверят"
    )


def appointment_reminder(starts_at: datetime, address: str) -> str:
    # время приема - настенные часы, хранятся как UTC, поэтому показываются
    # как есть, без перевода в пояс
    return (
        f"Напоминаем: завтра в {starts_at:%H:%M} вы записаны на прием в УК "
        f"по дому {_plain(address)}"
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
        "Управляющая организация напоминает: прием показаний открыт, а ваших "
        "еще нет. Передайте их в мини-приложении"
    )
