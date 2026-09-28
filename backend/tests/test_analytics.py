import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    RecordingBroker,
    add_user,
    admin_requests_service,
    reminders_service,
)

from zheka.api.schemas.analytics import (
    BenchmarkResponse,
    ChannelsSplitResponse,
    DashboardResponse,
    ExecutorStatsItem,
    MetersSeasonResponse,
)
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import (
    AnalyticsMetric,
    EventType,
    MeterType,
    MetricUnit,
    OrgRole,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestStatus,
    ResidentRole,
)
from zheka.core.errors import EntityNotFound, InvalidRequest, InvalidState
from zheka.core.ids import HouseId, OrgId, RequestId, UserId
from zheka.core.services.analytics import AnalyticsService, Benchmark, BenchmarkValue
from zheka.core.services.reminders import ReadingReminder
from zheka.infra.database.models import (
    DemandSignal,
    Event,
    Flat,
    House,
    Meter,
    OrgMember,
    OrgSettings,
    Organization,
    Reading,
    Request,
    Resident,
)
from zheka.infra.database.repos.analytics import AnalyticsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo

NOW = datetime(2031, 3, 12, 12, tzinfo=UTC)
REGION = "Аналитическая область"


def _service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
) -> AnalyticsService:
    return AnalyticsService(
        AnalyticsRepo(session),
        HousesRepo(session),
        OrgsRepo(session),
        reminders_service(session, publisher),
    )


async def _house(
    session: AsyncSession,
    org_id: OrgId | None,
    city: str = "Аналитград",
    region: str = REGION,
    timezone: str = "Europe/Moscow",
) -> HouseId:
    house = House(
        timezone=timezone,
        org_id=org_id,
        region=region,
        city=city,
        street="Сводная",
        building=secrets.token_hex(2),
        cadastral_no=secrets.token_hex(8),
        chat_binding_code=secrets.token_hex(4),
    )
    session.add(house)
    await session.flush()
    return house.id


async def _org(
    session: AsyncSession,
    *,
    city: str = "Аналитград",
    region: str = REGION,
    is_demo: bool = False,
    registered: bool = True,
    settings: dict[str, Any] | None = None,
) -> tuple[OrgId, HouseId]:
    org = Organization(
        timezone="Europe/Moscow",
        name=f"УК Имярек {secrets.token_hex(4)}",
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Аналитическая область, Аналитград, Сводная, 1",
        registered_at=NOW - timedelta(days=365) if registered else None,
        is_demo=is_demo,
    )
    session.add(org)
    await session.flush()
    if settings is not None:
        session.add(OrgSettings(org_id=org.id, **settings))
    return org.id, await _house(session, OrgId(org.id), city, region)


async def _request(
    session: AsyncSession,
    house_id: HouseId,
    *,
    created_at: datetime = NOW - timedelta(days=1),
    accepted_after: timedelta | None = None,
    category: RequestCategory = RequestCategory.OTHER,
    channel: RequestChannel = RequestChannel.MINIAPP,
    status: RequestStatus = RequestStatus.NEW,
    parent_request_id: RequestId | None = None,
    executor_user_id: UserId | None = None,
    reviewed_at: datetime | None = None,
    done_at: datetime | None = None,
    rating: int | None = None,
    completion_reason: RequestCompletionReason | None = None,
) -> RequestId:
    request = Request(
        house_id=house_id,
        category=category,
        description="Заявка",
        status=status,
        channel=channel,
        parent_request_id=parent_request_id,
        executor_user_id=executor_user_id,
        created_at=created_at,
        accepted_at=None if accepted_after is None else created_at + accepted_after,
        reviewed_at=reviewed_at,
        done_at=done_at,
        rating=rating,
        completion_reason=completion_reason,
    )
    session.add(request)
    await session.flush()
    return request.id


async def _peer(
    session: AsyncSession,
    minutes: int,
    *,
    city: str = "Аналитград",
    region: str = REGION,
    is_demo: bool = False,
    registered: bool = True,
) -> OrgId:
    org_id, house_id = await _org(
        session,
        city=city,
        region=region,
        is_demo=is_demo,
        registered=registered,
    )
    await _request(session, house_id, accepted_after=timedelta(minutes=minutes))
    return org_id


def _metric(benchmark: Benchmark, metric: AnalyticsMetric) -> BenchmarkValue:
    [found] = [item for item in benchmark.metrics if item.key == metric.value]
    return found


async def test_the_benchmark_names_no_other_organization(session: AsyncSession) -> None:
    caller = await _peer(session, 10)
    others = [await _peer(session, 20), await _peer(session, 30)]

    benchmark = await _service(session).benchmark(caller, NOW)

    payload = BenchmarkResponse.model_validate(benchmark).model_dump_json()
    names = [org.name for org in await OrgsRepo(session).list_by_ids(others)]
    assert benchmark.metrics
    assert len(names) == 2
    assert not [name for name in names if name in payload]


async def test_a_city_cut_needs_three_organizations(session: AsyncSession) -> None:
    region = f"Область {secrets.token_hex(3)}"
    caller = await _peer(session, 10, region=region, city="Тройной")
    await _peer(session, 20, region=region, city="Тройной")
    await _peer(session, 30, region=region, city="Тройной")
    await _peer(session, 40, region=region, city="Двойной")
    await _peer(session, 50, region=region, city="Двойной")
    await _peer(session, 60, region=region, city="Одинокий")

    benchmark = await _service(session).benchmark(caller, NOW)

    rows = {(row.region, row.city): row for row in benchmark.regions}
    assert (region, "Двойной") not in rows
    assert rows[region, "Тройной"].orgs_count == 3
    assert rows[region, "Тройной"].value == 20
    assert rows[region, None].orgs_count == 6


async def test_a_cut_is_hidden_when_one_organization_is_left_outside(
    session: AsyncSession,
) -> None:
    first, second = f"R1 {secrets.token_hex(3)}", f"R2 {secrets.token_hex(3)}"
    caller = await _peer(session, 10, region=first)
    await _peer(session, 30, region=first)
    await _peer(session, 40, region=first)
    await _peer(session, 20, region=second)

    benchmark = await _service(session).benchmark(caller, NOW)

    assert benchmark.regions == []


async def test_a_cut_is_shown_when_three_organizations_are_outside(
    session: AsyncSession,
) -> None:
    first, second = f"R1 {secrets.token_hex(3)}", f"R2 {secrets.token_hex(3)}"
    caller = await _peer(session, 10, region=first)
    for minutes in (30, 40):
        await _peer(session, minutes, region=first)
    for minutes in (20, 50, 60):
        await _peer(session, minutes, region=second)

    benchmark = await _service(session).benchmark(caller, NOW)

    rows = {(row.region, row.city): row.value for row in benchmark.regions}
    assert rows == {
        (first, None): 30,
        (first, "Аналитград"): 30,
        (second, None): 50,
        (second, "Аналитград"): 50,
    }


async def test_a_city_is_hidden_when_one_organization_of_its_region_is_outside(
    session: AsyncSession,
) -> None:
    region, other = f"R {secrets.token_hex(3)}", f"S {secrets.token_hex(3)}"
    caller = await _peer(session, 10, region=region, city="X")
    await _peer(session, 20, region=region, city="X")
    await _peer(session, 30, region=region, city="X")
    await _peer(session, 40, region=region, city="Y")
    for minutes in (50, 60, 70):
        await _peer(session, minutes, region=other)

    benchmark = await _service(session).benchmark(caller, NOW)

    rows = {(row.region, row.city) for row in benchmark.regions}
    assert (region, None) in rows
    assert (region, "X") not in rows
    assert (other, None) in rows


async def test_two_organizations_hide_the_platform_median_and_rank(
    session: AsyncSession,
) -> None:
    caller = await _peer(session, 10)
    await _peer(session, 30)

    alone = _metric(
        await _service(session).benchmark(caller, NOW),
        AnalyticsMetric.ACCEPT_TIME,
    )

    assert alone.value == 10
    assert (alone.platform_median, alone.rank, alone.total) == (None, None, None)

    await _peer(session, 20)
    compared = _metric(
        await _service(session).benchmark(caller, NOW),
        AnalyticsMetric.ACCEPT_TIME,
    )

    assert (compared.platform_median, compared.rank, compared.total) == (20, 1, 3)


async def test_a_demo_organization_is_compared_only_with_demo_ones(
    session: AsyncSession,
) -> None:
    real = await _peer(session, 10)
    await _peer(session, 20)
    await _peer(session, 30)
    demo = await _peer(session, 5, is_demo=True)

    demo_metric = _metric(
        await _service(session).benchmark(demo, NOW),
        AnalyticsMetric.ACCEPT_TIME,
    )
    real_metric = _metric(
        await _service(session).benchmark(real, NOW),
        AnalyticsMetric.ACCEPT_TIME,
    )

    assert (demo_metric.platform_median, demo_metric.rank) == (None, None)
    assert (real_metric.rank, real_metric.total) == (1, 3)


async def test_an_unregistered_organization_is_no_peer(session: AsyncSession) -> None:
    caller = await _peer(session, 10)
    await _peer(session, 20)
    await _peer(session, 30, registered=False)

    metric = _metric(
        await _service(session).benchmark(caller, NOW),
        AnalyticsMetric.ACCEPT_TIME,
    )

    assert metric.total is None


async def test_the_rank_follows_each_metric_direction(session: AsyncSession) -> None:
    caller = await _peer(session, 10)
    caller_house = (await HousesRepo(session).list_for_org(caller))[0].id
    for channel in (RequestChannel.BOT, RequestChannel.CHAT):
        await _request(session, caller_house, channel=channel)
    for minutes in (20, 30):
        _, house_id = await _org(session)
        await _request(
            session,
            house_id,
            accepted_after=timedelta(minutes=minutes),
            channel=RequestChannel.PHONE,
        )

    benchmark = await _service(session).benchmark(caller, NOW)

    accept = _metric(benchmark, AnalyticsMetric.ACCEPT_TIME)
    digital = _metric(benchmark, AnalyticsMetric.DIGITAL_SHARE)
    assert (accept.value, accept.platform_median, accept.rank) == (10, 20, 1)
    assert (digital.value, digital.platform_median, digital.rank) == (10000, 0, 1)


async def test_a_foreign_house_on_the_dashboard_is_not_found(
    session: AsyncSession,
) -> None:
    org_id, _ = await _org(session)
    _, foreign = await _org(session)

    with pytest.raises(EntityNotFound):
        await _service(session).dashboard(org_id, foreign, None, None, NOW)


async def test_a_foreign_house_in_the_reminder_is_not_found(
    session: AsyncSession,
) -> None:
    org_id, own = await _org(session, settings={"meter_window_always_open": True})
    _, foreign = await _org(session)

    with pytest.raises(EntityNotFound):
        await _service(session).remind_not_submitted(org_id, [own, foreign], None, NOW)


async def test_overdue_counts_by_the_category_hours(session: AsyncSession) -> None:
    org_id, house_id = await _org(session)
    await _request(
        session,
        house_id,
        category=RequestCategory.LEAK,
        created_at=NOW - timedelta(hours=5),
    )
    await _request(
        session,
        house_id,
        category=RequestCategory.LEAK,
        created_at=NOW - timedelta(hours=3),
    )
    await _request(session, house_id, created_at=NOW - timedelta(hours=5))
    await _request(
        session,
        house_id,
        category=RequestCategory.LEAK,
        created_at=NOW - timedelta(hours=10),
        status=RequestStatus.DONE,
    )
    await _request(
        session,
        house_id,
        category=RequestCategory.LEAK,
        created_at=NOW - timedelta(hours=10),
        status=RequestStatus.ON_REVIEW,
    )

    dashboard = await _service(session).dashboard(org_id, None, None, None, NOW)

    tiles = {tile.key: tile.value for tile in dashboard.tiles}
    assert tiles["overdue"] == 1
    assert tiles["active"] == 4


async def test_the_tiles_average_and_share_are_rounded_once(
    session: AsyncSession,
) -> None:
    org_id, house_id = await _org(session)
    first = await _request(session, house_id, accepted_after=timedelta(minutes=10))
    await _request(
        session,
        house_id,
        accepted_after=timedelta(minutes=21),
        parent_request_id=first,
    )
    await _request(session, house_id, parent_request_id=first)

    dashboard = await _service(session).dashboard(org_id, house_id, None, None, NOW)

    tiles = {tile.key: tile.value for tile in dashboard.tiles}
    assert tiles[AnalyticsMetric.ACCEPT_TIME] == 16
    assert tiles[AnalyticsMetric.REPEAT_SHARE] == 6667
    assert dashboard.is_empty is False


async def test_the_executor_median_starts_at_the_last_assignment(
    session: AsyncSession,
) -> None:
    org_id, house_id = await _org(session)
    first = await add_user(session, "Первый")
    second = await add_user(session, "Второй")
    for user_id in (first, second):
        session.add(OrgMember(org_id=org_id, user_id=user_id, role=OrgRole.EXECUTOR))
    request_id = await _request(
        session,
        house_id,
        created_at=NOW - timedelta(hours=12),
        status=RequestStatus.ON_REVIEW,
        executor_user_id=first,
        reviewed_at=NOW - timedelta(hours=1),
    )
    for hours, user_id in ((10, first), (6, second), (4, first)):
        session.add(
            Event(
                type=EventType.REQUEST_ASSIGNED.value,
                payload={"request_id": request_id, "executor_user_id": user_id},
                created_at=NOW - timedelta(hours=hours),
            ),
        )
    await session.flush()

    rows = await _service(session).executors(org_id, None, None, NOW)

    by_user = {row.user_id: row for row in rows}
    assert by_user[first].median_time == 180
    assert by_user[second].median_time is None


async def test_the_executor_table_counts_closed_ratings_and_repeats(
    session: AsyncSession,
) -> None:
    org_id, house_id = await _org(session)
    executor = await add_user(session, "Исполнитель")
    session.add(OrgMember(org_id=org_id, user_id=executor, role=OrgRole.EXECUTOR))
    repeated = await _request(
        session,
        house_id,
        status=RequestStatus.DONE,
        executor_user_id=executor,
        done_at=NOW - timedelta(hours=2),
        rating=4,
    )
    await _request(
        session,
        house_id,
        status=RequestStatus.DONE,
        executor_user_id=executor,
        done_at=NOW - timedelta(hours=2),
        rating=5,
    )
    await _request(session, house_id, parent_request_id=repeated)

    [row] = await _service(session).executors(org_id, None, None, NOW)

    assert (row.closed, row.rating, row.repeat_share) == (2, 450, 5000)
    assert ExecutorStatsItem.model_validate(row).rating == 450


async def test_an_empty_organization_is_explicitly_empty(session: AsyncSession) -> None:
    org_id, _ = await _org(session)
    service = _service(session)

    dashboard = await service.dashboard(org_id, None, None, None, NOW)
    channels = await service.channels(org_id, None, None, NOW)
    season = await service.season(org_id, None, NOW)
    benchmark = await service.benchmark(org_id, NOW)

    by_category, by_week = dashboard.charts
    assert dashboard.is_empty is True
    assert [tile.value for tile in dashboard.tiles] == [0, 0, 0, 0]
    assert by_category.points == []
    assert [point.value for point in by_week.points] == [0] * 12
    assert (channels.is_empty, channels.total) == (True, 0)
    assert {item.count for item in channels.items} == {0}
    assert (season.is_empty, season.submitted, season.not_submitted) == (True, 0, 0)
    assert (benchmark.is_empty, benchmark.metrics) == (True, [])
    assert DashboardResponse.model_validate(dashboard).is_empty
    assert ChannelsSplitResponse.model_validate(channels).is_empty
    assert MetersSeasonResponse.model_validate(season).is_empty
    assert BenchmarkResponse.model_validate(benchmark).is_empty


async def test_the_channel_split_shares_add_up(session: AsyncSession) -> None:
    org_id, house_id = await _org(session)
    await _request(session, house_id)
    await _request(session, house_id, channel=RequestChannel.BOT)
    await _request(session, house_id, channel=RequestChannel.PHONE)

    channels = await _service(session).channels(org_id, None, None, NOW)

    shares = {item.channel: item.share for item in channels.items}
    assert channels.total == 3
    assert channels.is_empty is False
    assert shares == {
        RequestChannel.MINIAPP: 3333,
        RequestChannel.BOT: 3333,
        RequestChannel.CHAT: 0,
        RequestChannel.PHONE: 3333,
    }


async def _metered_resident(
    session: AsyncSession,
    house_id: HouseId,
    period: date | None = None,
) -> UserId:
    flat = Flat(house_id=house_id, number=secrets.token_hex(2))
    session.add(flat)
    await session.flush()
    user_id = await add_user(session)
    session.add(
        Resident(
            user_id=user_id,
            house_id=house_id,
            flat_id=flat.id,
            role=ResidentRole.OWNER,
            verified_at=NOW,
        ),
    )
    meter = Meter(flat_id=flat.id, type=MeterType.COLD_WATER, serial="1")
    session.add(meter)
    await session.flush()
    if period is not None:
        session.add(
            Reading(
                meter_id=meter.id,
                period=period,
                values={"single": 1000},
                ocr_used=False,
                ocr_accepted=False,
                is_below_previous=False,
                submitted_at=NOW,
                submitted_by=user_id,
            ),
        )
        await session.flush()
    return user_id


async def test_the_season_counts_the_period_of_a_wrapping_window(
    session: AsyncSession,
) -> None:
    org_id, house_id = await _org(
        session,
        settings={"meter_window_day_from": 25, "meter_window_day_to": 5},
    )
    await _metered_resident(session, house_id, date(2031, 2, 1))
    await _metered_resident(session, house_id)
    session.add(Flat(house_id=house_id, number="без счетчика"))
    await session.flush()

    season = await _service(session).season(
        org_id,
        None,
        datetime(2031, 3, 3, 12, tzinfo=UTC),
    )

    assert season.period == date(2031, 2, 1)
    assert (season.window_from, season.window_to) == (
        date(2031, 2, 25),
        date(2031, 3, 5),
    )
    assert season.window_open is True
    assert (season.submitted, season.not_submitted) == (1, 1)
    assert season.houses[0].percent == 5000

    past = await _service(session).season(
        org_id,
        date(2031, 1, 1),
        datetime(2031, 3, 3, 12, tzinfo=UTC),
    )

    assert (past.period, past.window_open) == (date(2031, 1, 1), False)

    closed = await _service(session).season(org_id, None, NOW)

    assert closed.window_open is False


async def test_the_reminder_refuses_outside_the_window(session: AsyncSession) -> None:
    day = NOW.day % 28 + 1
    org_id, house_id = await _org(
        session,
        settings={"meter_window_day_from": day, "meter_window_day_to": day},
    )
    await _metered_resident(session, house_id)

    with pytest.raises(InvalidState):
        await _service(session).remind_not_submitted(org_id, [], None, NOW)


async def test_the_reminder_refuses_another_period(session: AsyncSession) -> None:
    org_id, _ = await _org(session, settings={"meter_window_always_open": True})

    with pytest.raises(InvalidRequest):
        await _service(session).remind_not_submitted(org_id, [], date(2031, 2, 1), NOW)


async def test_a_second_press_the_same_day_queues_nobody(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    org_id, house_id = await _org(session, settings={"meter_window_always_open": True})
    user_id = await _metered_resident(session, house_id)
    broker = RecordingBroker()
    publisher = TaskPublisher(broker)
    service = _service(session, publisher)

    first = await service.remind_not_submitted(org_id, [], None, now)
    second = await service.remind_not_submitted(org_id, [house_id], None, now)
    await publisher.flush()

    assert (first, second) == (1, 0)
    [queued] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert queued["user_ids"] == [user_id]


async def test_the_reminder_skips_a_resident_reminded_today_by_the_schedule(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    org_id, house_id = await _org(session, settings={"meter_window_always_open": True})
    user_id = await _metered_resident(session, house_id)
    session.add(
        Event(
            user_id=user_id,
            type=EventType.READING_REMINDER_SENT.value,
            payload={"house_id": house_id, "kind": ReadingReminder.OPEN.value},
            created_at=now,
        ),
    )
    await session.flush()

    queued = await _service(session).remind_not_submitted(org_id, [], None, now)

    assert queued == 0


async def test_yesterdays_press_does_not_silence_today(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    org_id, house_id = await _org(session, settings={"meter_window_always_open": True})
    user_id = await _metered_resident(session, house_id)
    session.add(
        Event(
            user_id=user_id,
            type=EventType.READING_REMINDER_SENT.value,
            payload={
                "house_id": house_id,
                "period": date(now.year, now.month, 1).isoformat(),
                "kind": ReadingReminder.MANUAL.value,
            },
            created_at=now - timedelta(days=1),
        ),
    )
    await session.flush()

    queued = await _service(session).remind_not_submitted(org_id, [], None, now)

    assert queued == 1


async def test_unconnected_houses_list_their_waiting_residents(
    session: AsyncSession,
) -> None:
    orphan = await _house(session, None)
    _, unregistered = await _org(session, registered=False)
    caller, connected = await _org(session)
    for house_id in (orphan, unregistered, unregistered, connected):
        session.add(DemandSignal(house_id=house_id, user_id=await add_user(session)))
    await session.flush()

    benchmark = await _service(session).benchmark(caller, NOW)

    waiting = {house.house_id: house.waiting for house in benchmark.unconnected_houses}
    assert waiting[orphan] == 1
    assert waiting[unregistered] == 2
    assert connected not in waiting


async def test_another_organizations_requests_stay_out(session: AsyncSession) -> None:
    org_id, _ = await _org(session)
    other_org, other_house = await _org(session)
    executor = await add_user(session, "Исполнитель")
    for org in (org_id, other_org):
        session.add(OrgMember(org_id=org, user_id=executor, role=OrgRole.EXECUTOR))
    await _request(
        session,
        other_house,
        status=RequestStatus.DONE,
        executor_user_id=executor,
        done_at=NOW - timedelta(hours=1),
    )
    service = _service(session)

    dashboard = await service.dashboard(org_id, None, None, None, NOW)
    channels = await service.channels(org_id, None, None, NOW)
    [row] = await service.executors(org_id, None, None, NOW)

    assert dashboard.is_empty is True
    assert channels.total == 0
    assert (row.closed, row.repeat_share) == (0, 0)


async def test_a_median_half_rounds_away_from_zero(session: AsyncSession) -> None:
    caller = await _peer(session, 5)
    for minutes in (10, 11, 30):
        await _peer(session, minutes)

    metric = _metric(
        await _service(session).benchmark(caller, NOW),
        AnalyticsMetric.ACCEPT_TIME,
    )

    assert metric.platform_median == 11


async def test_the_auto_closed_share_is_over_closed_requests(
    session: AsyncSession,
) -> None:
    caller, house_id = await _org(session)
    await _request(
        session,
        house_id,
        status=RequestStatus.DONE,
        completion_reason=RequestCompletionReason.AUTO_CLOSED,
    )
    await _request(
        session,
        house_id,
        status=RequestStatus.DONE,
        completion_reason=RequestCompletionReason.RESIDENT_ACCEPTED,
        rating=5,
    )
    await _request(session, house_id)

    benchmark = await _service(session).benchmark(caller, NOW)

    assert _metric(benchmark, AnalyticsMetric.AUTO_CLOSED_SHARE).value == 5000
    rating = _metric(benchmark, AnalyticsMetric.RATING)
    assert (rating.value, rating.unit) == (500, MetricUnit.POINTS)


async def test_the_season_query_counts_only_the_orgs_flats(
    session: AsyncSession,
) -> None:
    org_id, house_id = await _org(session)
    _, foreign = await _org(session)
    await _metered_resident(session, house_id)
    await _metered_resident(session, foreign)

    counts = await AnalyticsRepo(session).season(org_id, date(2031, 3, 1))

    assert set(counts) == {house_id}


async def test_a_benchmark_with_only_unconnected_houses_is_not_empty(
    session: AsyncSession,
) -> None:
    caller, _ = await _org(session)
    orphan = await _house(session, None)
    session.add(DemandSignal(house_id=orphan, user_id=await add_user(session)))
    await session.flush()

    benchmark = await _service(session).benchmark(caller, NOW)

    assert benchmark.metrics == []
    assert benchmark.is_empty is False


async def test_a_benchmark_with_only_region_rows_is_not_empty(
    session: AsyncSession,
) -> None:
    caller, _ = await _org(session)
    for minutes in (10, 20, 30):
        await _peer(session, minutes)

    benchmark = await _service(session).benchmark(caller, NOW)

    assert benchmark.metrics == []
    assert benchmark.regions
    assert benchmark.is_empty is False


async def test_an_executor_assigned_after_review_is_not_charged(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    org_id, house_id = await _org(session)
    first = await add_user(session, "Первый")
    second = await add_user(session, "Второй")
    for user_id in (first, second):
        session.add(OrgMember(org_id=org_id, user_id=user_id, role=OrgRole.EXECUTOR))
    request_id = await _request(
        session,
        house_id,
        created_at=now - timedelta(hours=12),
        status=RequestStatus.ON_REVIEW,
        executor_user_id=first,
        reviewed_at=now - timedelta(hours=6),
    )
    session.add(
        Event(
            type=EventType.REQUEST_ASSIGNED.value,
            payload={"request_id": request_id, "executor_user_id": first},
            created_at=now - timedelta(hours=10),
        ),
    )
    await session.flush()

    await admin_requests_service(session).assign(org_id, request_id, second, first)
    rows = await _service(session).executors(org_id, None, None, now)

    by_user = {row.user_id: row for row in rows}
    assert by_user[second].median_time is None
    assert by_user[first].median_time is None


async def test_dashboard_weeks_follow_the_office_clock(session: AsyncSession) -> None:
    org_id, house_id = await _org(session)
    await _request(session, house_id, created_at=datetime(2031, 3, 9, 22, tzinfo=UTC))

    dashboard = await _service(session).dashboard(org_id, None, None, None, NOW)

    by_week = {point.label: point.value for point in dashboard.charts[1].points}
    assert (by_week["2031-03-03"], by_week["2031-03-10"]) == (0, 1)


async def test_the_readings_window_of_each_house_follows_its_own_clock(
    session: AsyncSession,
) -> None:
    now = datetime(2031, 3, 14, 20, tzinfo=UTC)
    org_id, _ = await _org(
        session,
        settings={"meter_window_day_from": 15, "meter_window_day_to": 25},
    )
    far = await _house(session, OrgId(org_id), timezone="Asia/Vladivostok")
    await _metered_resident(session, far)
    service = _service(session)

    season = await service.season(org_id, None, now)
    queued = await service.remind_not_submitted(org_id, [], None, now)

    assert (season.window_open, queued) == (True, 1)


async def test_a_period_ending_before_it_starts_is_refused(
    session: AsyncSession,
) -> None:
    org_id, _ = await _org(session)

    with pytest.raises(InvalidRequest):
        await _service(session).channels(
            org_id,
            date(2031, 3, 2),
            date(2031, 3, 1),
            NOW,
        )
