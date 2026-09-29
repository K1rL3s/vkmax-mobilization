from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from html import escape
from math import ceil

from zheka.base import ZhekaType
from zheka.core.enums import (
    CATEGORY_RULES,
    PollAuthor,
    RequestCategory,
    RequestStatus,
)
from zheka.core.ids import RequestId
from zheka.core.models import House, Request

BLOCKED = "УК закрыла вам доступ к этому дому"
OPEN_REQUEST = "📱 Открыть заявку"
SUBMIT_READINGS = "📟 Передать показания"
MY_METERS = "📟 Мои счетчики"
VOTE = "🗳 Проголосовать"
MY_APPOINTMENTS = "📅 Мои записи"
OPEN_APP = "📱 Открыть приложение"
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


METER_PHOTO_HINT = "📷 Или пришлите фото счетчика сюда"


def reading_window_opened() -> str:
    return f"📟 Открыт прием показаний счетчиков\n{METER_PHOTO_HINT}"


def reading_window_closing(days: int) -> str:
    return (
        f"⏰ Через {_days(days)} закрывается прием показаний, а ваших еще нет. "
        f"Без них начисление пойдет по нормативу\n{METER_PHOTO_HINT}"
    )


def proposal_for_chairman(text: str) -> str:
    return (
        "💡 Новое предложение по дому\n"
        f"🖊 {escape(text)}\n"
        "👤 Автор скрыт: предложения анонимны"
    )


def proposal_answered(text: str, answer: str | None, *, accepted: bool) -> str:
    head = (
        "✅ Председатель принял ваше предложение"
        if accepted
        else "❌ Председатель отклонил ваше предложение"
    )
    lines = [head, f"🖊 {escape(text)}"]
    if answer is not None:
        lines.append(f"💬 {escape(answer)}")
    return "\n".join(lines)


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
        f"\n{METER_PHOTO_HINT}"
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


ME_TOO = "✋ У меня тоже"
CARD_HASHTAG = "#заявка"


_TEENS = range(11, 15)
_FEW = range(2, 5)


def _plural(count: int, one: str, few: str, many: str) -> str:
    if count % 100 in _TEENS:
        return many
    if count % 10 == 1:
        return one
    return few if count % 10 in _FEW else many


def flats_count(count: int) -> str:
    return f"{count} {_plural(count, 'квартира', 'квартиры', 'квартир')}"


def group_card(category: RequestCategory, flats: int, status: RequestStatus) -> str:
    rule = CATEGORY_RULES[category]
    told = _plural(flats, "сообщила", "сообщили", "сообщили")
    return (
        f"{rule.caption}: о проблеме {told} {flats_count(flats)}\n"
        "УК получила заявки. Статус: "
        f"{REQUEST_STATUS_LABELS[status].lower()}\n"
        f"Если у вас то же самое, нажмите «{ME_TOO[2:]}»\n"
        f"{CARD_HASHTAG}"
    )


def group_card_done(category: RequestCategory, flats: int) -> str:
    return (
        f"✅ {CATEGORY_RULES[category].label}: УК отметила работы выполненными "
        f"(сообщали {flats_count(flats)})"
    )


def request_card(request: Request, house: House) -> str:
    rule = CATEGORY_RULES[request.category]
    return (
        f"{rule.emoji} Заявка №{request.id} · {rule.label}\n"
        f"Статус: {REQUEST_STATUS_LABELS[request.status].lower()}\n"
        f"⏰ Срок: до {house.local(request.deadline_at):{MOMENT}}\n"
        f"{CARD_HASHTAG}"
    )


def request_card_done(request_id: RequestId) -> str:
    return f"✅ Заявка №{request_id}: УК отметила выполненной"


def request_card_grouped(request_id: RequestId, category: RequestCategory) -> str:
    return (
        f"🔗 Заявка №{request_id} · {CATEGORY_RULES[category].label} вошла в общую "
        "заявку дома, статус теперь в ее карточке"
    )


def request_share_text(request: Request, house: House) -> str:
    return (
        f"{CATEGORY_RULES[request.category].emoji} Заявка №{request.id} · "
        f"{CATEGORY_RULES[request.category].label}, {house.address}. "
        "Если у вас то же самое, присоединяйтесь к заявке"
    )


POLL_HASHTAG = "#опрос"
POLL_NOT_OSS = "Голосуют собственники, это не ОСС"
VOTE_IN_APP = "📱 Голосовать в приложении"
VOTE_OPTION_LIMIT = 40


class PollCardRow(ZhekaType):
    text: str
    flats: int
    percent: int


POLL_AUTHORS: Mapping[PollAuthor, str] = {
    PollAuthor.STAFF: "Опрос УК",
    PollAuthor.CHAIRMAN: "Опрос председателя",
    PollAuthor.RESIDENT: "Инициатива жителя",
}


def poll_card(
    title: str,
    role: str,
    rows: Sequence[PollCardRow],
    voted: int,
    total: int,
    ends_at: datetime | None,
) -> str:
    author = POLL_AUTHORS[PollAuthor(role)]
    head = (
        f"🗳 {author}: {escape(title)}"
        if ends_at is not None
        else f"🗳 {author} завершен: {escape(title)}"
    )
    lines = [head]
    for number, row in enumerate(rows, start=1):
        share = f"{row.flats} кв., {row.percent // 100}% площади"
        lines.append(f"{number}. {escape(row.text)} - {share}")
    until = "" if ends_at is None else f", до {ends_at:%d.%m}"
    flats = _plural(total, "квартиры", "квартир", "квартир")
    lines.append(f"Проголосовало {voted} из {total} {flats}{until}")
    lines.extend((POLL_NOT_OSS, POLL_HASHTAG))
    return "\n".join(lines)


def vote_button(number: int, text: str) -> str:
    label = f"{number}. {text}"
    if len(label) <= VOTE_OPTION_LIMIT:
        return label
    return f"{label[: VOTE_OPTION_LIMIT - 1]}…"


def chairman_offer(name: str, address: str) -> str:
    return (
        f"🏛 {escape(name)} предлагает вам стать председателем совета дома "
        f"{escape(address)}\n\n"
        "✅ Вы сможете создавать опросы жителей и привязать чат дома\n\n"
        "ℹ️ Председателя совета дома избирает общее собрание собственников "
        "(ст. 161.1 ЖК РФ): приложение передает права в сервисе и не заменяет "
        "протокол собрания"
    )


def chairman_accepted(name: str, address: str) -> str:
    return f"✅ {escape(name)} теперь председатель совета дома {escape(address)}"


def chairman_declined(name: str, address: str) -> str:
    return (
        f"😔 {escape(name)} отказался стать председателем совета дома {escape(address)}"
    )


DIGEST_BUTTON = "📊 Сводка за неделю"
DIGEST_SUBSCRIBE = "🔔 Присылать по воскресеньям"
DIGEST_EMPTY = "📊 За неделю в доме ничего не произошло"
DIGEST_SUBSCRIBED = (
    "🔔 Сводку буду присылать по воскресеньям, выключить можно в настройках уведомлений"
)
DIGEST_QUOTE_LIMIT = 60


def digest_head(address: str) -> str:
    return f"📊 Неделя в доме: {escape(address)}"


def digest_requests(created: int, closed: int, overdue: int) -> str:
    parts = []
    if created:
        parts.append(f"{created} {_plural(created, 'новая', 'новые', 'новых')}")
    if closed:
        parts.append(f"{closed} {_plural(closed, 'закрыта', 'закрыто', 'закрыто')}")
    if overdue:
        verb = _plural(overdue, "просрочена", "просрочено", "просрочено")
        parts.append(f"{verb} {overdue}")
    return f"🛠 Заявки: {', '.join(parts)}"


def digest_categories(rows: Sequence[tuple[RequestCategory, int]]) -> str:
    named = ", ".join(
        f"{CATEGORY_RULES[category].label.lower()} ({count})"
        for category, count in rows
    )
    return f"Чаще всего: {named}"


def digest_announcements(count: int, last: str) -> str:
    return f"📢 Объявлений УК: {count}, последнее: «{_quoted(last)}»"


def digest_poll(title: str, ends_at: datetime, voted: int) -> str:
    verb = _plural(voted, "проголосовала", "проголосовали", "проголосовали")
    voices = (
        "голосов от квартир пока нет" if voted == 0 else f"{verb} {flats_count(voted)}"
    )
    return f"🗳 Опрос «{escape(title)}» до {ends_at:%d.%m}, {voices}"


def digest_readings(day_to: int | None) -> str:
    if day_to is None:
        return "🔢 Показания принимаются в любой день"
    return f"🔢 Показания принимаются до {day_to} числа"


def _quoted(text: str) -> str:
    line = " ".join(text.split())
    if len(line) <= DIGEST_QUOTE_LIMIT:
        return escape(line)
    return f"{escape(line[: DIGEST_QUOTE_LIMIT - 1])}…"
