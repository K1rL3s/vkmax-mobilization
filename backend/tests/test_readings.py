import base64
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser, freeze_now, make_config
from tests.test_requests import _add_user, _events, _photo

from zheka.config import FilesConfig, YandexConfig
from zheka.core.enums import (
    EventType,
    MeterType,
    OrgRole,
    RequestCategory,
    ResidentRole,
    ServiceType,
    TariffZone,
)
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    InvalidValue,
    NotEnoughRights,
)
from zheka.core.ids import FlatId, HouseId, MeterId, OrgId, UserId
from zheka.core.services.admin_readings import AdminReadingsService
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.meter_access import MeterAccess
from zheka.core.services.meters import MeterDraft, MeterUpdateDraft, MetersService
from zheka.core.services.readings import (
    WRONG_PERIOD,
    ReadingsService,
    SubmitDraft,
    available_periods,
    consumption,
    is_below_previous,
    is_spike,
    window_is_open,
    window_period,
)
from zheka.infra.database.models import Charge, Flat, OrgSettings, Resident, Tariff
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.yandex.vision import VisionClient, parse_reading

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]
MOSCOW = ZoneInfo("Europe/Moscow")


def _make_access(session: AsyncSession) -> MeterAccess:
    return MeterAccess(
        MetersRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        OrgsRepo(session),
    )


def _make_service(session: AsyncSession) -> ReadingsService:
    return ReadingsService(
        MetersRepo(session),
        ChargesRepo(session),
        OrgsRepo(session),
        _make_access(session),
        FilesService(make_config().files, "test-token"),
        EventsService(EventsRepo(session)),
    )


def _make_meters_service(session: AsyncSession) -> MetersService:
    return MetersService(MetersRepo(session), _make_access(session))


def _make_admin_service(session: AsyncSession) -> AdminReadingsService:
    return AdminReadingsService(
        MetersRepo(session),
        HousesRepo(session),
        UsersRepo(session),
    )


def _period_back(months_back: int) -> date:
    today = datetime.now(MOSCOW).date()
    year, month = divmod(today.year * 12 + today.month - 1 - months_back, 12)
    return date(year, month + 1, 1)


def _draft(
    value: int = 1_000,
    period: date | None = None,
    *,
    ocr: bool = False,
) -> SubmitDraft:
    return SubmitDraft(
        period=_period_back(0) if period is None else period,
        values={TariffZone.SINGLE: value},
        photos=[_photo()],
        ocr_used=ocr,
        ocr_accepted=ocr,
    )


async def _add_resident(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    flat_id: FlatId | None,
    *,
    role: ResidentRole = ResidentRole.OWNER,
    verified: bool = True,
) -> Resident:
    is_owner = role is ResidentRole.OWNER
    resident = Resident(
        user_id=user_id,
        house_id=house_id,
        flat_id=flat_id,
        role=role,
        can_see_charges=is_owner,
        can_vote=is_owner,
        verified_at=datetime.now(UTC) if verified else None,
    )
    session.add(resident)
    await session.flush()
    return resident


async def _set_window(
    session: AsyncSession,
    org_id: OrgId,
    *,
    day_from: int,
    day_to: int,
) -> None:
    orgs_repo = OrgsRepo(session)
    settings = await orgs_repo.get_settings(org_id)
    if settings is None:
        settings = await orgs_repo.add_settings(org_id)
    settings.meter_window_always_open = False
    settings.meter_window_day_from = day_from
    settings.meter_window_day_to = day_to
    await session.flush()


async def _close_window(session: AsyncSession, org_id: OrgId) -> None:
    closed_day = 1 if datetime.now(MOSCOW).day != 1 else 2
    await _set_window(session, org_id, day_from=closed_day, day_to=closed_day)


async def _add_meter(
    session: AsyncSession,
    flat_id: FlatId,
    *,
    meter_type: MeterType = MeterType.COLD_WATER,
    tariff_zones: int = 1,
    next_verification_date: date | None = None,
) -> MeterId:
    meter = await MetersRepo(session).add(
        flat_id,
        meter_type,
        tariff_zones,
        "SN-0001",
        next_verification_date,
    )
    assert meter is not None
    return meter.id


async def _add_reading(
    session: AsyncSession,
    meter_id: MeterId,
    period: date,
    value: int,
    user_id: UserId,
) -> None:
    await MetersRepo(session).add_reading(
        meter_id,
        period,
        {TariffZone.SINGLE: value},
        [_photo()],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC),
        submitted_by=user_id,
    )


async def _add_tariff(session: AsyncSession, house_id: HouseId, value: int) -> None:
    session.add(
        Tariff(
            house_id=house_id,
            service=ServiceType.COLD_WATER,
            value=value,
            unit="m3",
            valid_from=date(2020, 1, 1),
        ),
    )
    await session.flush()


async def _owner_with_meter(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    *,
    tariff_zones: int = 1,
    next_verification_date: date | None = None,
) -> tuple[OrgHouseFlatUser, MeterId]:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(
        session,
        own.flat_id,
        tariff_zones=tariff_zones,
        next_verification_date=next_verification_date,
    )
    return own, meter_id


@pytest.mark.parametrize(
    ("day", "day_from", "day_to", "always_open", "is_open"),
    [
        (20, 15, 25, False, True),
        (10, 15, 25, False, False),
        (26, 15, 25, False, False),
        (15, 15, 25, False, True),
        (25, 15, 25, False, True),
        (30, 28, 5, False, True),
        (3, 28, 5, False, True),
        (15, 28, 5, False, False),
        (28, 28, 5, False, True),
        (5, 28, 5, False, True),
        (1, 15, 25, True, True),
    ],
)
def test_window_is_open(
    day: int,
    day_from: int,
    day_to: int,
    always_open: bool,
    is_open: bool,
) -> None:
    assert window_is_open(day, day_from, day_to, always_open=always_open) is is_open


def test_available_periods_marks_a_charged_period_closed_but_keeps_it() -> None:
    options = available_periods(date(2026, 3, 17), {date(2026, 2, 1)})

    assert [(option.period, option.is_open) for option in options] == [
        (date(2026, 3, 1), True),
        (date(2026, 2, 1), False),
        (date(2026, 1, 1), True),
    ]
    assert options[0].reason is None
    assert options[1].reason is not None


@pytest.mark.parametrize(
    ("previous", "delta"),
    [
        ({TariffZone.SINGLE: 10_000}, {TariffZone.SINGLE: 5_500}),
        (None, {TariffZone.SINGLE: 0}),
    ],
)
def test_consumption(
    previous: dict[TariffZone, int] | None,
    delta: dict[TariffZone, int],
) -> None:
    assert consumption({TariffZone.SINGLE: 15_500}, previous) == delta


@pytest.mark.parametrize(
    ("value", "previous", "below"),
    [(900, 1_000, True), (1_100, 1_000, False), (0, None, False)],
)
def test_is_below_previous(value: int, previous: int | None, below: bool) -> None:
    previous_values = None if previous is None else {TariffZone.SINGLE: previous}
    assert is_below_previous({TariffZone.SINGLE: value}, previous_values) is below


@pytest.mark.parametrize(
    ("current", "history", "spike"),
    [
        (200, [100, 90, 110], True),
        (150, [100, 90, 110], False),
        (1_000_000, [100, 90], False),
        (299, [100, 200, 100, 200], False),
        (300, [100, 200, 100, 200], True),
    ],
)
def test_is_spike(current: int, history: list[int], spike: bool) -> None:
    assert is_spike(current, history) is spike


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("123.45", 123_450),
        ("123,45", 123_450),
        ("0123", 123_000),
        ("garbage", None),
        pytest.param("1" * 4301, None, id="over-int-digit-limit"),
    ],
)
def test_parse_reading(text: str, value: int | None) -> None:
    assert parse_reading(text) == value


@pytest.mark.parametrize(
    ("config", "photo", "values"),
    [
        (YandexConfig(api_key=None, folder_id=None), b"jpeg", None),
        (YandexConfig(api_key="key", folder_id="folder"), None, None),
        (
            YandexConfig(api_key="key", folder_id="folder"),
            b"jpeg",
            {TariffZone.SINGLE: 123_450},
        ),
    ],
)
async def test_vision_client_sends_ocr_only_a_photo_it_can_send(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    config: YandexConfig,
    photo: bytes | None,
    values: dict[TariffZone, int] | None,
) -> None:
    sent: list[bytes] = []

    async def recognize(request: web.Request) -> web.StreamResponse:
        sent.append(base64.b64decode((await request.json())["content"]))
        text = {"textAnnotation": {"fullText": "00123,45 м3"}}
        return web.json_response({"result": text})

    app = web.Application()
    app.router.add_post("/ocr", recognize)
    name = _photo()
    if photo is not None:
        (tmp_path / name).write_bytes(photo)
    files = FilesService(FilesConfig(dir=str(tmp_path), max_size_mb=10), "token")
    async with TestServer(app) as server, aiohttp.ClientSession() as http:
        url = str(server.make_url("/ocr"))
        monkeypatch.setattr("zheka.infra.yandex.vision._RECOGNIZE_URL", url)
        assert await VisionClient(config, files, http).recognize(name) == values

    assert sent == ([] if values is None else [photo])


async def test_readings_are_refused_to_an_unverified_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=False)
    meter_id = await _add_meter(session, own.flat_id)
    service = _make_service(session)

    with pytest.raises(NotEnoughRights):
        await service.history(own.user_id, meter_id)
    with pytest.raises(NotEnoughRights):
        await service.submit(own.user_id, meter_id, _draft())


@pytest.mark.parametrize(
    ("role", "verified"),
    [(ResidentRole.OWNER, False), (ResidentRole.TENANT, True)],
)
async def test_add_meter_needs_a_verified_owner(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    role: ResidentRole,
    verified: bool,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(
        session,
        own.user_id,
        own.house_id,
        own.flat_id,
        role=role,
        verified=verified,
    )

    with pytest.raises(NotEnoughRights):
        await _make_meters_service(session).add(
            own.user_id,
            own.flat_id,
            MeterDraft(type=MeterType.COLD_WATER, tariff_zones=1, serial="SN-1"),
        )


async def test_submit_allows_a_verified_tenant_but_hides_the_amount(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(
        session,
        own.user_id,
        own.house_id,
        own.flat_id,
        role=ResidentRole.TENANT,
    )
    meter_id = await _add_meter(session, own.flat_id)
    await _add_tariff(session, own.house_id, 100_000)

    result = await _make_service(session).submit(own.user_id, meter_id, _draft())

    assert result.row.amount is None


async def test_add_meter_allows_org_staff_of_the_managing_org(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    employee_id = await _add_user(session, "Сотрудник УК")
    await OrgsRepo(session).add_member(own.org_id, employee_id, OrgRole.EMPLOYEE)

    card = await _make_meters_service(session).add(
        employee_id,
        own.flat_id,
        MeterDraft(type=MeterType.COLD_WATER, tariff_zones=1, serial="SN-1"),
    )

    assert card.meter.flat_id == own.flat_id


async def test_a_foreign_meter_id_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    other = await make_org_house_flat_user()
    other_meter_id = await _add_meter(session, other.flat_id)
    service = _make_service(session)

    with pytest.raises(EntityNotFound):
        await service.history(own.user_id, other_meter_id)
    with pytest.raises(EntityNotFound):
        await service.submit(own.user_id, other_meter_id, _draft())
    with pytest.raises(EntityNotFound):
        await _make_meters_service(session).update(
            own.user_id,
            other_meter_id,
            MeterUpdateDraft(tariff_zones=1, serial="SN-2"),
        )


async def test_admin_list_refuses_a_cross_org_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    other = await make_org_house_flat_user()

    with pytest.raises(EntityNotFound):
        await _make_admin_service(session).admin_list(
            other.org_id,
            own.house_id,
            None,
            None,
            only_below_previous=False,
            limit=50,
            offset=0,
        )


@pytest.mark.parametrize(
    "draft",
    [
        SubmitDraft(
            period=date(2026, 1, 1),
            values={TariffZone.DAY: 1_000},
            photos=["a.jpg"],
        ),
        SubmitDraft(
            period=date(2026, 1, 1),
            values={TariffZone.DAY: 1_000, TariffZone.NIGHT: 500},
            photos=[],
        ),
    ],
)
async def test_submit_rejects_wrong_zones_and_a_missing_photo(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    draft: SubmitDraft,
) -> None:
    own, meter_id = await _owner_with_meter(
        session,
        make_org_house_flat_user,
        tariff_zones=2,
    )

    with pytest.raises(InvalidRequest):
        await _make_service(session).submit(own.user_id, meter_id, draft)


async def test_submit_accepts_and_flags_a_value_below_the_previous_one(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    await _add_reading(session, meter_id, _period_back(12), 5_000, own.user_id)

    result = await _make_service(session).submit(own.user_id, meter_id, _draft(4_000))

    assert result.row.reading.is_below_previous is True
    assert result.warning is not None


async def test_submit_blocks_an_expired_verification(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(
        session,
        make_org_house_flat_user,
        next_verification_date=date(2000, 1, 1),
    )

    with pytest.raises(InvalidState):
        await _make_service(session).submit(own.user_id, meter_id, _draft())


async def test_resubmission_wins_over_the_earlier_row(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    service = _make_service(session)

    await service.submit(own.user_id, meter_id, _draft(1_000))
    await service.submit(own.user_id, meter_id, _draft(2_000))

    assert len(await service.history(own.user_id, meter_id)) == 2
    cards = await service.list_meters(own.flat_id)
    assert len(cards) == 1
    assert cards[0].last_values == {TariffZone.SINGLE: 2_000}


async def test_submit_rejects_a_period_other_than_the_current_one_inside_the_window(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)

    with pytest.raises(InvalidState):
        await _make_service(session).submit(
            own.user_id,
            meter_id,
            _draft(period=_period_back(12)),
        )


async def test_submit_out_of_window_uses_one_of_the_allowed_past_periods(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    await _close_window(session, own.org_id)

    result = await _make_service(session).submit(own.user_id, meter_id, _draft())

    assert result.row.reading.period == _period_back(0)
    events = await _events(session, EventType.READING_SUBMITTED)
    assert events[-1].payload["out_of_window"] is True


async def test_submit_out_of_window_for_a_period_with_a_charge_raises(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    await _close_window(session, own.org_id)
    session.add(
        Charge(
            flat_id=own.flat_id,
            period=_period_back(0),
            lines={},
            total=0,
            is_closed=True,
        ),
    )
    await session.flush()

    with pytest.raises(InvalidState):
        await _make_service(session).submit(own.user_id, meter_id, _draft())


async def test_submit_out_of_window_rejects_a_period_outside_periods_back(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    await _close_window(session, own.org_id)

    with pytest.raises(InvalidState):
        await _make_service(session).submit(
            own.user_id,
            meter_id,
            _draft(period=_period_back(60)),
        )


async def test_submit_computes_consumption_and_the_exact_kopeck_amount(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    await _add_reading(session, meter_id, _period_back(12), 0, own.user_id)
    await _add_tariff(session, own.house_id, 100_000)

    result = await _make_service(session).submit(own.user_id, meter_id, _draft())

    assert result.row.consumption == {TariffZone.SINGLE: 1_000}
    assert result.row.amount == 1_000


async def test_submit_records_the_reading_submitted_event(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)

    await _make_service(session).submit(own.user_id, meter_id, _draft(ocr=True))

    events = await _events(session, EventType.READING_SUBMITTED)
    assert len(events) == 1
    assert events[0].payload == {
        "meter_type": MeterType.COLD_WATER.value,
        "ocr_used": True,
        "ocr_accepted": True,
        "is_below_previous": False,
        "out_of_window": False,
    }


async def test_submit_suggests_a_leak_request_on_a_consumption_spike(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    for back, value in zip((4, 3, 2, 1), (100, 200, 300, 400), strict=True):
        await _add_reading(session, meter_id, _period_back(back), value, own.user_id)

    result = await _make_service(session).submit(own.user_id, meter_id, _draft(5_400))

    assert result.suggested_category is RequestCategory.LEAK


async def test_add_meter_rejects_a_second_meter_of_the_same_type(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, _ = await _owner_with_meter(session, make_org_house_flat_user)

    with pytest.raises(InvalidValue):
        await _make_meters_service(session).add(
            own.user_id,
            own.flat_id,
            MeterDraft(type=MeterType.COLD_WATER, tariff_zones=1, serial="SN-2"),
        )


async def test_update_meter_changes_serial_and_zones(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)

    card = await _make_meters_service(session).update(
        own.user_id,
        meter_id,
        MeterUpdateDraft(tariff_zones=2, serial="NEW-SERIAL"),
    )

    assert card.meter.tariff_zones == 2
    assert card.meter.serial == "NEW-SERIAL"


async def test_house_average_covers_flats_that_submitted_for_the_same_meter_type(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    neighbour = await _add_user(session, "Сосед")
    neighbour_flat = Flat(house_id=own.house_id, number="2")
    session.add(neighbour_flat)
    await session.flush()
    await _add_resident(session, neighbour, own.house_id, neighbour_flat.id)
    neighbour_meter_id = await _add_meter(session, neighbour_flat.id)
    for meter, user in ((meter_id, own.user_id), (neighbour_meter_id, neighbour)):
        await _add_reading(session, meter, _period_back(1), 0, user)
    service = _make_service(session)

    await service.submit(own.user_id, meter_id, _draft(1_000))
    result = await service.submit(neighbour, neighbour_meter_id, _draft(3_000))

    assert result.house_average == 2_000


async def test_flats_without_reading_lists_flats_with_a_meter_and_no_submission(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_meter(session, own.flat_id)
    period = _period_back(0)
    meters_repo = MetersRepo(session)

    assert own.flat_id in await meters_repo.flats_without_reading(own.house_id, period)

    hot = await _add_meter(session, own.flat_id, meter_type=MeterType.HOT_WATER)
    await _add_reading(session, hot, period, 1_000, own.user_id)

    assert own.flat_id not in await meters_repo.flats_without_reading(
        own.house_id,
        period,
    )


async def test_admin_list_shows_the_whole_chain_and_the_below_previous_flag(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    await _add_reading(session, meter_id, _period_back(1), 5_000, own.user_id)
    service = _make_service(session)
    await service.submit(own.user_id, meter_id, _draft(6_000))
    await service.submit(own.user_id, meter_id, _draft(4_000))
    admin_service = _make_admin_service(session)

    rows, total = await admin_service.admin_list(
        own.org_id,
        own.house_id,
        _period_back(0),
        None,
        only_below_previous=False,
        limit=50,
        offset=0,
    )
    below_rows, below_total = await admin_service.admin_list(
        own.org_id,
        own.house_id,
        _period_back(0),
        None,
        only_below_previous=True,
        limit=50,
        offset=0,
    )

    assert total == 2
    assert len(rows) == 2
    assert below_total == 1
    assert below_rows[0].reading.is_below_previous is True


def _window(day_from: int, day_to: int, *, always_open: bool = False) -> OrgSettings:
    return OrgSettings(
        org_id=OrgId(1),
        meter_window_day_from=day_from,
        meter_window_day_to=day_to,
        meter_window_always_open=always_open,
    )


@pytest.mark.parametrize(
    ("today", "settings", "period"),
    [
        (date(2026, 9, 27), _window(25, 5), date(2026, 9, 1)),
        (date(2026, 10, 3), _window(25, 5), date(2026, 9, 1)),
        (date(2026, 10, 1), _window(25, 1), date(2026, 9, 1)),
        (date(2027, 1, 2), _window(20, 5), date(2026, 12, 1)),
        (date(2026, 9, 20), _window(15, 25), date(2026, 9, 1)),
        (date(2026, 9, 3), None, date(2026, 9, 1)),
        (date(2026, 10, 3), _window(25, 5, always_open=True), date(2026, 10, 1)),
    ],
)
def test_a_wrapping_window_is_one_period_the_month_it_opened(
    today: date,
    settings: OrgSettings | None,
    period: date,
) -> None:
    assert window_period(today, settings) == period


async def test_submit_in_the_tail_of_a_wrapping_window_goes_to_its_opening_month(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    today = datetime.now(MOSCOW).date()
    await _set_window(session, own.org_id, day_from=today.day + 1, day_to=today.day)
    service = _make_service(session)

    periods = await service.periods(own.flat_id)
    with pytest.raises(InvalidState, match=WRONG_PERIOD):
        await service.submit(own.user_id, meter_id, _draft())
    result = await service.submit(own.user_id, meter_id, _draft(period=_period_back(1)))

    assert [option.period for option in periods.options] == [_period_back(1)]
    assert result.row.reading.period == _period_back(1)


async def test_the_window_opens_on_the_date_of_the_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze_now(
        monkeypatch,
        "zheka.core.services.readings",
        datetime(2026, 9, 14, 20, tzinfo=UTC),
    )
    own = await make_org_house_flat_user(timezone="Asia/Vladivostok")
    await _set_window(session, own.org_id, day_from=15, day_to=25)

    periods = await _make_service(session).periods(own.flat_id)

    assert [(option.period, option.is_open) for option in periods.options] == [
        (date(2026, 9, 1), True),
    ]


async def test_a_verification_ended_on_the_house_date_blocks_the_reading(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze_now(
        monkeypatch,
        "zheka.core.services.readings",
        datetime(2026, 9, 14, 20, tzinfo=UTC),
    )
    own = await make_org_house_flat_user(timezone="Asia/Vladivostok")
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(
        session,
        own.flat_id,
        next_verification_date=date(2026, 9, 14),
    )
    service = _make_service(session)

    [card] = await service.list_meters(own.flat_id)
    assert card.verification_expired is True
    with pytest.raises(InvalidState, match="Срок поверки истек"):
        await service.submit(own.user_id, meter_id, _draft(period=date(2026, 9, 1)))
