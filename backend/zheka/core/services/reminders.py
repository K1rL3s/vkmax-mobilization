import logging
from calendar import monthrange
from collections.abc import Callable, Collection
from datetime import date, datetime, timedelta
from enum import StrEnum

from zheka.core import texts
from zheka.core.deeplinks import (
    APPOINTMENTS_APP_PATH,
    METERS_APP_PATH,
    poll_app_path,
)
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
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.reception import ReceptionRepo
from zheka.infra.database.repos.residents import ResidentsRepo

logger = logging.getLogger(__name__)

READING_SECOND_REMINDER_DAYS = 2
POLL_REMINDER_BEFORE = timedelta(hours=48)
READING_HOUR = 10
POLL_HOUR = 10
VERIFICATION_HOUR = 9
VERIFICATION_STAGE_DAYS = (VERIFICATION_WARNING.days, 7, 1, 0, -1)
APPOINTMENT_HOUR = 19


class ReadingReminder(StrEnum):
    OPEN = "open"
    CLOSING = "closing"
    MANUAL = "manual"


def reading_reminder(
    today: date,
    settings: OrgSettings | None,
) -> ReadingReminder | None:
    last_day = monthrange(today.year, today.month)[1]
    if settings is None or settings.meter_window_always_open:
        day_from, day_to = 1, last_day
    else:
        day_from = settings.meter_window_day_from
        day_to = settings.meter_window_day_to
    closing = day_to - READING_SECOND_REMINDER_DAYS
    if closing < 1 and day_from > day_to:
        closing += last_day
    if today.day == day_from:
        return ReadingReminder.OPEN
    if today.day == closing and window_is_open(
        today.day,
        day_from,
        day_to,
        always_open=False,
    ):
        return ReadingReminder.CLOSING
    return None


_READING_TEXTS: dict[ReadingReminder, Callable[[], str]] = {
    ReadingReminder.OPEN: texts.reading_window_opened,
    ReadingReminder.CLOSING: lambda: texts.reading_window_closing(
        READING_SECOND_REMINDER_DAYS,
    ),
    ReadingReminder.MANUAL: texts.reading_reminder_manual,
}


class RemindersService:
    __slots__ = (
        "_chats",
        "_events",
        "_events_repo",
        "_houses",
        "_meters",
        "_notifications",
        "_orgs",
        "_polls",
        "_reception",
        "_residents",
    )

    def __init__(
        self,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
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
        self._orgs = orgs_repo
        self._meters = meters_repo
        self._residents = residents_repo
        self._polls = polls_repo
        self._chats = chats_repo
        self._reception = reception_repo
        self._events_repo = events_repo
        self._events = events_service
        self._notifications = notifications_service

    async def remind_readings(self, now: datetime) -> int:
        queued: dict[ReadingReminder, set[UserId]] = {
            kind: set() for kind in ReadingReminder
        }
        sent = 0
        for house, settings in await self._houses.list_managed_with_settings():
            local = house.local(now)
            if local.hour < READING_HOUR:
                continue
            today = local.date()
            kind = reading_reminder(today, settings)
            if kind is None:
                continue
            period = window_period(today, settings)
            sent += await self._remind_house_readings(
                house.id,
                period,
                kind,
                queued[kind],
            )
        logger.info("Напоминание о показаниях: адресатов %s", sent)
        return sent

    async def remind_polls(self, now: datetime) -> int:
        polls = await self._polls.list_to_remind(now, now + POLL_REMINDER_BEFORE)
        reminded = 0
        for poll in polls:
            house = await self._houses.get(poll.house_id)
            if house is None or house.local(now).hour < POLL_HOUR:
                continue
            ends_at = house.local(poll.ends_at)
            voted = set(await self._polls.voted_flat_ids(poll.id))
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
                texts.poll_reminder(poll.title, ends_at),
                category=NotificationCategory.ANNOUNCEMENTS,
                mandatory=False,
                app_button=texts.VOTE,
                app_path=poll_app_path(poll.id),
            )
            self._notifications.notify_chats(
                [chat.chat_id for chat in chats],
                texts.poll_chat_reminder(poll.title, ends_at),
                app_button=texts.VOTE,
                app_path=poll_app_path(poll.id),
            )
            reminded += 1
        logger.info("Напоминание об опросах: опросов %s", reminded)
        return reminded

    async def close_expired_polls(self, now: datetime) -> int:
        closed = await self._polls.close_expired(now)
        logger.info("Закрыто опросов по сроку: %s", closed)
        return closed

    async def warn_verification(self, now: datetime) -> int:
        meters = await self._meters.list_to_warn(
            now.date() + timedelta(days=1) + VERIFICATION_WARNING,
        )
        warned = 0
        for meter in meters:
            due = meter.next_verification_date
            house = await self._houses.get_by_flat(meter.flat_id)
            if due is None or house is None:
                continue
            local = house.local(now)
            today = local.date()
            stage = verification_stage(today, due)
            if (
                local.hour < VERIFICATION_HOUR
                or stage is None
                or (
                    meter.verification_warned_at is not None
                    and meter.verification_warned_at >= stage
                )
            ):
                continue
            label = SERVICE_LABELS[SERVICE_OF_METER[meter.type]]
            days = (due - today).days
            if days < 0:
                text = texts.verification_expired(label, meter.serial)
            elif days == 0:
                text = texts.verification_today(label, meter.serial)
            else:
                text = texts.verification_soon(label, meter.serial, due, days)
            residents = await self._residents.list_verified_for_flats([meter.flat_id])
            await self._meters.mark_warned(meter, today)
            self._notifications.notify_users(
                [resident.user_id for resident in residents],
                text,
                category=NotificationCategory.METERS,
                mandatory=False,
                app_button=texts.MY_METERS,
                app_path=METERS_APP_PATH,
            )
            warned += 1
        logger.info("Предупреждение о поверке: счетчиков %s", warned)
        return warned

    async def remind_appointments(self, now: datetime) -> int:
        appointments = await self._reception.list_to_remind(
            now,
            now + timedelta(days=2),
        )
        reminded = 0
        for appointment in appointments:
            org = await self._orgs.get(appointment.org_id)
            if org is None:
                continue
            local = org.local(now)
            starts_at = org.local(appointment.starts_at)
            if (
                local.hour < APPOINTMENT_HOUR
                or starts_at.date() != local.date() + timedelta(days=1)
            ):
                continue
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
                    starts_at,
                    "" if house is None else house.address,
                ),
                category=NotificationCategory.REQUESTS,
                mandatory=True,
                app_button=texts.MY_APPOINTMENTS,
                app_path=APPOINTMENTS_APP_PATH,
            )
            reminded += 1
        logger.info("Напоминание о приеме: записей %s", reminded)
        return reminded

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
        stamp = {"house_id": house_id, "period": period.isoformat(), "kind": kind.value}
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
                EventType.READING_REMINDER_SENT,
                user_id=user_id,
                **stamp,
            )
        fresh = [user_id for user_id in user_ids if user_id not in queued]
        queued.update(fresh)
        self._notifications.notify_users(
            fresh,
            _READING_TEXTS[kind](),
            category=NotificationCategory.METERS,
            mandatory=False,
            app_button=texts.SUBMIT_READINGS,
            app_path=METERS_APP_PATH,
        )
        return len(fresh)

    async def remind_reading_laggards(
        self,
        house_ids: Collection[HouseId],
        period: date,
        now: datetime,
    ) -> int:
        queued: set[UserId] = set()
        sent = 0
        for house in await self._houses.list_by_ids(house_ids):
            since = house.day_start(house.local(now).date())
            sent += await self._remind_house_readings(
                house.id,
                period,
                ReadingReminder.MANUAL,
                queued,
                since,
            )
        logger.info("Ручное напоминание о показаниях: адресатов %s", sent)
        return sent


def verification_stage(today: date, due: date) -> date | None:
    stages = [due - timedelta(days=days) for days in VERIFICATION_STAGE_DAYS]
    return max((stage for stage in stages if stage <= today), default=None)
