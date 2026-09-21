import logging
from calendar import monthrange
from collections.abc import Callable, Collection
from datetime import date, datetime, time, timedelta
from enum import StrEnum

from zheka.core import texts
from zheka.core.enums import (
    SERVICE_LABELS,
    SERVICE_OF_METER,
    EventType,
    NotificationCategory,
    ResidentStatus,
)
from zheka.core.ids import HouseId, UserId
from zheka.core.models import OrgSettings
from zheka.core.services.events import EventsService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.readings import (
    VERIFICATION_WARNING,
    window_is_open,
    window_period,
)
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.reception import ReceptionRepo
from zheka.infra.database.repos.residents import ResidentsRepo

logger = logging.getLogger(__name__)

# второе напоминание о показаниях - за столько дней до закрытия окна
READING_SECOND_REMINDER_DAYS = 2
# раньше напоминание об опросе легло бы рядом с объявлением о нем самом
POLL_REMINDER_BEFORE = timedelta(hours=48)


class ReadingReminder(StrEnum):
    OPEN = "open"
    CLOSING = "closing"
    MANUAL = "manual"


def reading_reminder(
    today: date, settings: OrgSettings | None
) -> ReadingReminder | None:
    last_day = monthrange(today.year, today.month)[1]
    # у окна «всегда открыто» ни открытия, ни закрытия нет, поэтому оно
    # считается целым месяцем. Дом без настроек, как и в submit, открыт всегда
    if settings is None or settings.meter_window_always_open:
        day_from, day_to = 1, last_day
    else:
        day_from = settings.meter_window_day_from
        day_to = settings.meter_window_day_to
    closing = day_to - READING_SECOND_REMINDER_DAYS
    if closing < 1 and day_from > day_to:
        # окно через конец месяца закрывается в первые его дни, и за два дня
        # до этого - конец предыдущего
        closing += last_day
    if today.day == day_from:
        return ReadingReminder.OPEN
    # у окна короче трех дней канун закрытия приходится на день до открытия
    if today.day == closing and window_is_open(
        today.day, day_from, day_to, always_open=False
    ):
        return ReadingReminder.CLOSING
    return None


_READING_TEXTS: dict[ReadingReminder, Callable[[], str]] = {
    ReadingReminder.OPEN: texts.reading_window_opened,
    ReadingReminder.CLOSING: lambda: texts.reading_window_closing(
        READING_SECOND_REMINDER_DAYS
    ),
    ReadingReminder.MANUAL: texts.reading_reminder_manual,
}


class RemindersService:
    # отметка и рассылка в одной транзакции, а рассылка уходит после коммита:
    # упавший прогон ничего не отправил и не отметил
    __slots__ = (
        "_chats",
        "_events",
        "_events_repo",
        "_houses",
        "_meters",
        "_notifications",
        "_polls",
        "_reception",
        "_residents",
    )

    def __init__(
        self,
        houses_repo: HousesRepo,
        meters_repo: MetersRepo,
        residents_repo: ResidentsRepo,
        polls_repo: PollsRepo,
        chats_repo: ChatsRepo,
        reception_repo: ReceptionRepo,
        events_repo: EventsRepo,
        events_service: EventsService,
        notifications_service: NotificationsService,
    ) -> None:
        self._houses = houses_repo
        self._meters = meters_repo
        self._residents = residents_repo
        self._polls = polls_repo
        self._chats = chats_repo
        self._reception = reception_repo
        self._events_repo = events_repo
        self._events = events_service
        self._notifications = notifications_service

    async def remind_readings(self, today: date) -> int:
        # житель двух домов, где окна сошлись в один день, получает один текст
        # на оба, а отметку - в каждом доме, чтобы повторный прогон видел обе
        queued: dict[ReadingReminder, set[UserId]] = {
            kind: set() for kind in ReadingReminder
        }
        sent = 0
        for house_id, settings in await self._houses.list_managed_with_settings():
            kind = reading_reminder(today, settings)
            if kind is None:
                continue
            # период тот же, что запишет submit в этот день: напоминание по
            # другому периоду дошло бы до тех, кто уже сдал
            period = window_period(today, settings)
            sent += await self._remind_house_readings(
                house_id, period, kind, queued[kind]
            )
        logger.info("Напоминание о показаниях: адресатов %s", sent)
        return sent

    async def remind_polls(self, now: datetime) -> int:
        polls = await self._polls.list_to_remind(now, now + POLL_REMINDER_BEFORE)
        for poll in polls:
            # квартира проголосовала, если ее голос идет в кворум: голос
            # неподтвержденного совладельца не снимает напоминания с того, чей
            # голос засчитался бы. Сам проголосовавший не получает его никогда
            voted = set(await self._polls.voted_flat_ids(poll.id, verified_only=True))
            voters = set(await self._polls.voter_ids(poll.id))
            user_ids = [
                resident.user_id
                for resident in await self._residents.list_for_house(poll.house_id)
                if resident.can_vote
                and resident.status is ResidentStatus.ACTIVE
                and resident.flat_id is not None
                and resident.flat_id not in voted
                and resident.user_id not in voters
            ]
            chats = await self._chats.list_for_houses([poll.house_id])
            await self._polls.mark_reminded(poll, now)
            self._notifications.notify_users(
                user_ids,
                texts.poll_reminder(poll.title, poll.ends_at),
                category=NotificationCategory.ANNOUNCEMENTS,
                mandatory=False,
            )
            self._notifications.notify_chats(
                [chat.chat_id for chat in chats],
                texts.poll_chat_reminder(poll.title, poll.ends_at),
            )
        logger.info("Напоминание об опросах: опросов %s", len(polls))
        return len(polls)

    async def close_expired_polls(self, now: datetime) -> int:
        closed = await self._polls.close_expired(now)
        logger.info("Закрыто опросов по сроку: %s", closed)
        return closed

    async def warn_verification(self, today: date) -> int:
        meters = await self._meters.list_to_warn(today + VERIFICATION_WARNING)
        warned = 0
        for meter in meters:
            due = meter.next_verification_date
            if due is None:
                continue
            label = SERVICE_LABELS[SERVICE_OF_METER[meter.type]]
            if today >= due:
                text = texts.verification_expired(label, meter.serial)
            elif (
                meter.verification_warned_at is None
                or meter.verification_warned_at < due - VERIFICATION_WARNING
            ):
                text = texts.verification_soon(label, meter.serial, due)
            else:
                continue
            residents = await self._residents.list_verified_for_flats([meter.flat_id])
            await self._meters.mark_warned(meter, today)
            self._notifications.notify_users(
                [resident.user_id for resident in residents],
                text,
                category=NotificationCategory.METERS,
                mandatory=False,
            )
            warned += 1
        logger.info("Предупреждение о поверке: счетчиков %s", warned)
        return warned

    async def remind_appointments(self, now: datetime) -> int:
        # прием хранит настенные часы как UTC, поэтому «завтра» считается
        # по той же дате starts_at, без перевода в пояс
        appointments = await self._reception.list_to_remind(
            now.date() + timedelta(days=1)
        )
        for appointment in appointments:
            house = await self._houses.get(appointment.house_id)
            await self._reception.mark_reminded(appointment, now)
            await self._events.record(
                EventType.APPOINTMENT_REMINDER_SENT,
                user_id=appointment.user_id,
                appointment_id=appointment.id,
            )
            self._notifications.notify_user(
                appointment.user_id,
                texts.appointment_reminder(
                    appointment.starts_at, "" if house is None else house.address
                ),
                category=NotificationCategory.REQUESTS,
                mandatory=True,
            )
        logger.info("Напоминание о приеме: записей %s", len(appointments))
        return len(appointments)

    async def _remind_house_readings(
        self,
        house_id: HouseId,
        period: date,
        kind: ReadingReminder,
        queued: set[UserId],
        since: datetime | None = None,
    ) -> int:
        flat_ids = await self._meters.flats_without_reading(house_id, period)
        residents = await self._residents.list_verified_for_flats(flat_ids)
        # у каждого дома свое окно: без дома отметка первого глушила бы
        # напоминание второго, открывшегося в другой день
        stamp = {"house_id": house_id, "period": period.isoformat(), "kind": kind.value}
        # с since гасит любое напоминание о показаниях с этого момента, какого
        # угодно дома и вида
        reminded = await self._events_repo.users_with(
            EventType.READING_REMINDER_SENT,
            [resident.user_id for resident in residents],
            stamp if since is None else {},
            since,
        )
        user_ids = [
            resident.user_id
            for resident in residents
            if resident.user_id not in reminded
        ]
        for user_id in user_ids:
            await self._events.record(
                EventType.READING_REMINDER_SENT, user_id=user_id, **stamp
            )
        fresh = [user_id for user_id in user_ids if user_id not in queued]
        queued.update(fresh)
        self._notifications.notify_users(
            fresh,
            _READING_TEXTS[kind](),
            category=NotificationCategory.METERS,
            mandatory=False,
        )
        return len(fresh)

    async def remind_reading_laggards(
        self, house_ids: Collection[HouseId], period: date, now: datetime
    ) -> int:
        # кнопка УК: кто сегодня уже получил любое напоминание о показаниях,
        # второе не получит, поэтому десять нажатий - одно сообщение
        since = datetime.combine(now.date(), time(), now.tzinfo)
        queued: set[UserId] = set()
        sent = 0
        for house_id in house_ids:
            sent += await self._remind_house_readings(
                house_id, period, ReadingReminder.MANUAL, queued, since
            )
        logger.info("Ручное напоминание о показаниях: адресатов %s", sent)
        return sent
