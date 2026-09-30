import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import InMemoryBroker

from tests.conftest import (
    Fixture,
    RecordingBroker,
    freeze_now,
    make_notifications_service,
)

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.broker.tasks.digest import send_weekly_digests
from zheka.core import texts
from zheka.core.enums import (
    CATEGORY_RULES,
    AnnouncementChannel,
    NotificationCategory,
    NotificationLevel,
    PollStatus,
    RequestCategory,
    RequestChannel,
    RequestStatus,
    ResidentRole,
    ResidentStatus,
)
from zheka.core.ids import FlatId, HouseId, MaxUserId, OrgId, UserId
from zheka.core.services.digest import DigestService
from zheka.infra.database.models import (
    Announcement,
    Flat,
    House,
    OrgSettings,
    Organization,
    Poll,
    PollOption,
    PollVote,
    Request,
    Resident,
    User,
)
from zheka.infra.database.repos.analytics import AnalyticsRepo
from zheka.infra.database.repos.announcements import AnnouncementsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.notifications import NotificationsRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

NOW = datetime(2026, 10, 11, 15, tzinfo=UTC)
MOSCOW = "Europe/Moscow"
VLADIVOSTOK = "Asia/Vladivostok"
OPEN_WINDOW = {"meter_window_day_from": 1, "meter_window_day_to": 25}


@pytest.fixture(autouse=True)
def _frozen_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    freeze_now(monkeypatch, "zheka.broker.tasks.digest", NOW)


def _service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
) -> DigestService:
    return DigestService(
        HousesRepo(session),
        ResidentsRepo(session),
        PollsRepo(session),
        AnnouncementsRepo(session),
        AnalyticsRepo(session),
        OrgsRepo(session),
        make_notifications_service(session, publisher),
    )


async def _org_house(
    session: AsyncSession,
    *,
    timezone: str = MOSCOW,
    settings: dict[str, Any] | None = None,
) -> tuple[OrgId, House]:
    org = Organization(
        timezone=timezone,
        name=f"УК {secrets.token_hex(4)}",
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Сводная область, Сводоград, Сводная, 1",
    )
    session.add(org)
    await session.flush()
    if settings is not None:
        session.add(OrgSettings(org_id=org.id, **settings))
    house = House(
        timezone=timezone,
        org_id=org.id,
        region="Сводная область",
        city="Сводоград",
        street="Сводная",
        building=secrets.token_hex(2),
        cadastral_no=secrets.token_hex(8),
        chat_binding_code=secrets.token_hex(4),
    )
    session.add(house)
    await session.flush()
    return org.id, house


async def _user(session: AsyncSession, name: str = "Житель") -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name=name)
    session.add(user)
    await session.flush()
    return user.id


async def _flat(session: AsyncSession, house_id: HouseId) -> FlatId:
    flat = Flat(house_id=house_id, number=secrets.token_hex(2))
    session.add(flat)
    await session.flush()
    return flat.id


async def _request(
    session: AsyncSession,
    house_id: HouseId,
    *,
    created_at: datetime,
    category: RequestCategory = RequestCategory.OTHER,
    done_at: datetime | None = None,
) -> None:
    session.add(
        Request(
            house_id=house_id,
            category=category,
            description="Заявка",
            status=RequestStatus.NEW if done_at is None else RequestStatus.DONE,
            channel=RequestChannel.MINIAPP,
            created_at=created_at,
            done_at=done_at,
            deadline_at=CATEGORY_RULES[category].deadlines(
                created_at,
                ZoneInfo(MOSCOW),
            )[1],
        ),
    )
    await session.flush()


async def _announcement(
    session: AsyncSession,
    org_id: OrgId,
    house_id: HouseId,
    text: str,
    created_at: datetime,
) -> None:
    session.add(
        Announcement(
            org_id=org_id,
            house_ids=[house_id],
            text=text,
            channels=[AnnouncementChannel.DIRECT.value],
            created_by=await _user(session, "Сотрудник"),
            created_at=created_at,
        ),
    )
    await session.flush()


async def _poll_with_vote(
    session: AsyncSession,
    house_id: HouseId,
    title: str,
    ends_at: datetime,
) -> None:
    author = await _user(session, "Председатель")
    poll = Poll(
        house_id=house_id,
        created_by_user_id=author,
        created_by_role=ResidentRole.OWNER.value,
        title=title,
        starts_at=ends_at - timedelta(days=7),
        ends_at=ends_at,
        status=PollStatus.ACTIVE,
    )
    session.add(poll)
    await session.flush()
    option = PollOption(poll_id=poll.id, text="За", position=0)
    session.add(option)
    await session.flush()
    session.add(
        PollVote(
            poll_id=poll.id,
            option_id=option.id,
            user_id=author,
            flat_id=await _flat(session, house_id),
            counted_by_area=True,
        ),
    )
    await session.flush()


async def _run(broker: InMemoryBroker, task: Any) -> None:
    sent = await task.kicker().with_broker(broker).kiq()
    result = await sent.wait_result(timeout=5)
    assert not result.is_err, result.error


async def test_a_week_without_events_has_no_digest(session: AsyncSession) -> None:
    _, house = await _org_house(session, settings=OPEN_WINDOW)

    assert await _service(session).for_house(house, NOW) is None


async def test_the_digest_counts_requests_announcements_and_polls(
    session: AsyncSession,
) -> None:
    org_id, house = await _org_house(session, settings=OPEN_WINDOW)
    await _request(
        session,
        house.id,
        created_at=NOW - timedelta(days=2),
        category=RequestCategory.HEATING,
        done_at=NOW - timedelta(days=1),
    )
    await _request(
        session,
        house.id,
        created_at=NOW - timedelta(days=3),
        category=RequestCategory.HEATING,
    )
    await _request(
        session,
        house.id,
        created_at=NOW - timedelta(hours=12),
        category=RequestCategory.ELEVATOR,
    )
    await _announcement(
        session,
        org_id,
        house.id,
        "Отключение воды 12.10",
        NOW - timedelta(days=2),
    )
    await _poll_with_vote(
        session,
        house.id,
        "Шлагбаум во дворе",
        datetime(2026, 10, 15, 12, tzinfo=UTC),
    )

    digest = await _service(session).for_house(house, NOW)

    assert digest == "\n\n".join(
        (
            f"📊 Неделя в доме: {house.address}",
            (
                "🛠 Заявки: 3 новые, 1 закрыта, просрочена 1\n"
                "Чаще всего: отопление (2), лифт (1)"
            ),
            "📢 Объявлений УК: 1, последнее: «Отключение воды 12.10»",
            "📮 Опрос «Шлагбаум во дворе» до 15.10, проголосовала 1 квартира",
            "🔢 Показания принимаются до 25 числа",
        ),
    )


async def test_the_week_is_counted_in_the_house_timezone(
    session: AsyncSession,
) -> None:
    closed_at = datetime(2026, 10, 5, 12, tzinfo=UTC)
    service = _service(session)
    digests = []
    for timezone in (MOSCOW, VLADIVOSTOK):
        _, house = await _org_house(session, timezone=timezone)
        await _request(
            session,
            house.id,
            created_at=closed_at,
            done_at=closed_at + timedelta(hours=1),
        )
        digests.append(await service.for_house(house, NOW))

    moscow, vladivostok = digests
    assert moscow is not None
    assert "🛠 Заявки: 1 новая, 1 закрыта" in moscow
    assert vladivostok is None


async def test_the_digest_waits_for_sunday_evening(
    session: AsyncSession,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    org_id, house = await _org_house(session, settings=OPEN_WINDOW)
    session.add(
        Resident(
            user_id=await _user(session),
            house_id=house.id,
            flat_id=await _flat(session, house.id),
            role=ResidentRole.OWNER,
        ),
    )
    await _announcement(
        session,
        org_id,
        house.id,
        "Отключение воды 12.10",
        NOW - timedelta(days=1),
    )
    service = _service(session, publisher)

    assert await service.send_weekly(NOW - timedelta(days=1)) == 0
    assert await service.send_weekly(NOW - timedelta(hours=5)) == 0
    assert await service.send_weekly(NOW) == 1
    assert await service.send_weekly(NOW + timedelta(hours=3)) == 0

    await publisher.flush()
    assert len(broker.enqueued(TaskName.BROADCAST_TO_USERS)) == 1


async def test_the_digest_is_off_until_the_resident_subscribes(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user()
    repo = NotificationsRepo(session)

    [muted] = await repo.recipients([data.user_id], NotificationCategory.DIGEST)
    await repo.set_level(
        data.user_id,
        NotificationCategory.DIGEST,
        NotificationLevel.SILENT,
    )
    [subscribed] = await repo.recipients([data.user_id], NotificationCategory.DIGEST)

    assert muted.level.resolve_notify(mandatory=False) is None
    assert subscribed.level.resolve_notify(mandatory=False) is False


async def test_the_sunday_task_sends_one_digest_a_day(
    bot_session: AsyncSession,
    task_broker: InMemoryBroker,
    bot_broker: RecordingBroker,
) -> None:
    org_id, house = await _org_house(bot_session, settings=OPEN_WINDOW)
    resident = await _user(bot_session)
    blocked = await _user(bot_session, "Заблокированный")
    for user_id, status in (
        (resident, ResidentStatus.ACTIVE),
        (blocked, ResidentStatus.BLOCKED),
    ):
        bot_session.add(
            Resident(
                user_id=user_id,
                house_id=house.id,
                flat_id=await _flat(bot_session, house.id),
                role=ResidentRole.OWNER,
                status=status,
            ),
        )
    await _announcement(
        bot_session,
        org_id,
        house.id,
        "Отключение воды 12.10",
        NOW - timedelta(days=1),
    )
    await bot_session.commit()

    for _ in range(2):
        await _run(task_broker, send_weekly_digests)

    queued = [
        kwargs
        for kwargs in bot_broker.enqueued(TaskName.BROADCAST_TO_USERS)
        if resident in kwargs["user_ids"]
    ]
    assert len(queued) == 1
    assert queued[0]["category"] == NotificationCategory.DIGEST.value
    assert queued[0]["mandatory"] is False
    assert queued[0]["app_button"] == texts.OPEN_APP
    assert blocked not in queued[0]["user_ids"]
    assert "📢 Объявлений УК: 1" in queued[0]["text"]


async def test_the_digest_skips_announcements_for_entrances_and_flats(
    session: AsyncSession,
) -> None:
    org_id, house = await _org_house(session)
    author = await _user(session, "Сотрудник")
    session.add_all(
        [
            Announcement(
                org_id=org_id,
                house_ids=[house.id],
                text="Нет ГВС во втором подъезде",
                channels=[AnnouncementChannel.DIRECT.value],
                created_by=author,
                created_at=NOW - timedelta(days=1),
                entrances=[2],
            ),
            Announcement(
                org_id=org_id,
                house_ids=[house.id],
                text="Откройте доступ в квартиру",
                channels=[AnnouncementChannel.DIRECT.value],
                created_by=author,
                created_at=NOW - timedelta(days=1),
                flat_ids=[await _flat(session, house.id)],
            ),
        ],
    )
    await session.flush()

    assert await _service(session).for_house(house, NOW) is None
