from collections.abc import Mapping
from html import escape
from types import MappingProxyType

from zheka.core.enums import RequestStatus
from zheka.core.ids import RequestId

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
