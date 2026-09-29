import logging
from datetime import datetime, timedelta

from zheka.core import texts
from zheka.core.enums import NotificationCategory, PollStatus, ResidentStatus
from zheka.core.models import House, OrgSettings
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.readings import window_accepts
from zheka.infra.database.repos.analytics import AnalyticsRepo
from zheka.infra.database.repos.announcements import AnnouncementsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

logger = logging.getLogger(__name__)

DIGEST_DAYS = 7
DIGEST_HOUR = 18
SUNDAY = 6
TOP_CATEGORIES = 2


class DigestService:
    __slots__ = (
        "_analytics",
        "_announcements",
        "_houses",
        "_notifications",
        "_orgs",
        "_polls",
        "_residents",
    )

    def __init__(
        self,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        polls_repo: PollsRepo,
        announcements_repo: AnnouncementsRepo,
        analytics_repo: AnalyticsRepo,
        orgs_repo: OrgsRepo,
        notifications_service: NotificationsService,
    ) -> None:
        self._houses = houses_repo
        self._residents = residents_repo
        self._polls = polls_repo
        self._announcements = announcements_repo
        self._analytics = analytics_repo
        self._orgs = orgs_repo
        self._notifications = notifications_service

    async def for_house(self, house: House, now: datetime) -> str | None:
        settings = (
            None
            if house.org_id is None
            else await self._orgs.get_settings(house.org_id)
        )
        return await self.build(house, settings, now)

    async def build(
        self,
        house: House,
        settings: OrgSettings | None,
        now: datetime,
    ) -> str | None:
        today = house.local(now).date()
        since = house.day_start(today - timedelta(days=DIGEST_DAYS - 1))
        until = house.day_start(today + timedelta(days=1))
        sections = [
            *await self._request_lines(house, since, until, now),
            *await self._announcement_lines(house, since),
            *await self._poll_lines(house, now),
        ]
        if not sections:
            return None
        if window_accepts(today, settings):
            sections.append(
                texts.digest_readings(
                    None
                    if settings is None or settings.meter_window_always_open
                    else settings.meter_window_day_to,
                ),
            )
        return "\n".join([texts.digest_head(house.address), *sections])

    async def send_weekly(self, now: datetime) -> int:
        sent = 0
        for house, settings in await self._houses.list_managed_with_settings():
            local = house.local(now)
            today = local.date()
            if (
                local.weekday() != SUNDAY
                or local.hour < DIGEST_HOUR
                or house.digest_sent_on == today
            ):
                continue
            text = await self.build(house, settings, now)
            if text is None:
                continue
            residents = await self._residents.list_for_house(house.id)
            await self._houses.mark_digest_sent(house, today)
            self._notifications.notify_users(
                sorted(
                    {
                        resident.user_id
                        for resident in residents
                        if resident.status is ResidentStatus.ACTIVE
                    },
                ),
                text,
                category=NotificationCategory.DIGEST,
                mandatory=False,
                app_button=texts.OPEN_APP,
            )
            sent += 1
        logger.info("Недельная сводка: домов %s", sent)
        return sent

    async def _request_lines(
        self,
        house: House,
        since: datetime,
        until: datetime,
        now: datetime,
    ) -> list[str]:
        if house.org_id is None:
            return []
        counts = await self._analytics.digest_counts(
            house.org_id,
            house.id,
            since,
            until,
            now,
        )
        if not (counts.created or counts.closed or counts.overdue):
            return []
        lines = [texts.digest_requests(counts.created, counts.closed, counts.overdue)]
        categories = await self._analytics.by_category(
            house.org_id,
            house.id,
            since,
            until,
        )
        if categories:
            lines.append(texts.digest_categories(categories[:TOP_CATEGORIES]))
        return lines

    async def _announcement_lines(self, house: House, since: datetime) -> list[str]:
        announcements = await self._announcements.list_for_house_since(house.id, since)
        if not announcements:
            return []
        return [texts.digest_announcements(len(announcements), announcements[0].text)]

    async def _poll_lines(self, house: House, now: datetime) -> list[str]:
        polls = sorted(
            await self._polls.list_for_house(house.id),
            key=lambda poll: poll.ends_at,
        )
        lines = []
        for poll in polls:
            if poll.effective_status(now) is not PollStatus.ACTIVE:
                continue
            voted = await self._polls.voted_flat_ids(poll.id)
            lines.append(
                texts.digest_poll(poll.title, house.local(poll.ends_at), len(voted)),
            )
        return lines
