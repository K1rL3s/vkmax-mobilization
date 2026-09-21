import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser, make_config

from zheka.config import YandexConfig
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
from zheka.core.ids import FlatId, HouseId, MaxUserId, MeterId, OrgId, UserId
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
from zheka.infra.database.models import (
    Charge,
    Event,
    Flat,
    OrgSettings,
    Resident,
    Tariff,
    User,
)
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.events import events_table
from zheka.infra.database.tables.meters import meters_table
from zheka.infra.yandex.vision import VisionClient, parse_reading

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


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
        HousesRepo(session),
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


def _photo() -> str:
    # ровно то, что отдает upload_file: uuid4().hex плюс известный суффикс
    return f"{uuid4().hex}.jpg"


async def _add_user(session: AsyncSession, name: str = "Сосед") -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name=name)
    session.add(user)
    await session.flush()
    return UserId(user.id)


async def _add_resident(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    flat_id: FlatId | None,
    *,
    role: ResidentRole = ResidentRole.OWNER,
    verified: bool = True,
    can_see_charges: bool | None = None,
) -> Resident:
    is_owner = role is ResidentRole.OWNER
    resident = Resident(
        user_id=user_id,
        house_id=house_id,
        flat_id=flat_id,
        role=role,
        can_see_charges=is_owner if can_see_charges is None else can_see_charges,
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
    always_open: bool = False,
    day_from: int = 1,
    day_to: int = 28,
) -> None:
    orgs_repo = OrgsRepo(session)
    settings = await orgs_repo.get_settings(org_id)
    if settings is None:
        settings = await orgs_repo.add_settings(org_id)
    settings.meter_window_always_open = always_open
    settings.meter_window_day_from = day_from
    settings.meter_window_day_to = day_to
    await session.flush()


def _closed_window_day(today: date) -> int:
    # день, заведомо отличный от сегодняшнего - однодневное окно на него
    # гарантированно закрыто прямо сейчас
    return 1 if today.day != 1 else 2


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
    return MeterId(meter.id)


async def _add_tariff(
    session: AsyncSession,
    house_id: HouseId,
    service: ServiceType,
    value: int,
    valid_from: date = date(2020, 1, 1),
) -> Tariff:
    tariff = Tariff(
        house_id=house_id,
        service=service,
        value=value,
        unit="m3",
        valid_from=valid_from,
    )
    session.add(tariff)
    await session.flush()
    return tariff


async def _add_charge(session: AsyncSession, flat_id: FlatId, period: date) -> Charge:
    charge = Charge(flat_id=flat_id, period=period, lines={}, total=0, is_closed=True)
    session.add(charge)
    await session.flush()
    return charge


def _current_period() -> date:
    today = datetime.now(UTC).date()
    return date(today.year, today.month, 1)


def _period_back(months_back: int) -> date:
    # то же смещение месяца, что и в ReadingsService._shift_months
    today = datetime.now(UTC).date()
    month_index = today.year * 12 + (today.month - 1) - months_back
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)


async def _events(session: AsyncSession, event_type: EventType) -> list[Event]:
    stmt = select(Event).where(events_table.c.type == event_type)
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Чистые хелперы - без базы
# ---------------------------------------------------------------------------


def test_window_is_open_for_a_normal_window() -> None:
    assert window_is_open(20, 15, 25, always_open=False) is True
    assert window_is_open(10, 15, 25, always_open=False) is False
    assert window_is_open(26, 15, 25, always_open=False) is False
    # границы включены
    assert window_is_open(15, 15, 25, always_open=False) is True
    assert window_is_open(25, 15, 25, always_open=False) is True


def test_window_is_open_for_a_wrapping_window() -> None:
    # окно 28-5 переваливает через конец месяца
    assert window_is_open(30, 28, 5, always_open=False) is True
    assert window_is_open(3, 28, 5, always_open=False) is True
    assert window_is_open(15, 28, 5, always_open=False) is False
    assert window_is_open(28, 28, 5, always_open=False) is True
    assert window_is_open(5, 28, 5, always_open=False) is True


def test_window_is_open_when_always_open() -> None:
    # день вне обычного окна, always_open все равно отвечает True
    assert window_is_open(1, 15, 25, always_open=True) is True


def test_available_periods_marks_a_charged_period_closed_but_keeps_it() -> None:
    today = date(2026, 3, 17)
    current = date(2026, 3, 1)
    previous = date(2026, 2, 1)
    two_back = date(2026, 1, 1)

    options = available_periods(today, {previous})

    assert [option.period for option in options] == [current, previous, two_back]
    by_period = {option.period: option for option in options}
    assert by_period[current].is_open is True
    assert by_period[current].reason is None
    assert by_period[previous].is_open is False
    assert by_period[previous].reason is not None
    assert by_period[two_back].is_open is True


def test_consumption_computes_the_delta_per_zone() -> None:
    assert consumption(
        {TariffZone.SINGLE: 15_500},
        {TariffZone.SINGLE: 10_000},
    ) == {TariffZone.SINGLE: 5_500}


def test_consumption_is_zero_without_a_previous_reading() -> None:
    # первая подача счетчика не порождает мнимый расход от нуля
    assert consumption({TariffZone.SINGLE: 15_500}, None) == {TariffZone.SINGLE: 0}


def test_is_below_previous_true_when_a_zone_drops() -> None:
    assert (
        is_below_previous(
            {TariffZone.SINGLE: 900},
            {TariffZone.SINGLE: 1_000},
        )
        is True
    )


def test_is_below_previous_false_when_values_grow() -> None:
    assert (
        is_below_previous(
            {TariffZone.SINGLE: 1_100},
            {TariffZone.SINGLE: 1_000},
        )
        is False
    )


def test_is_below_previous_false_without_a_previous_reading() -> None:
    assert is_below_previous({TariffZone.SINGLE: 0}, None) is False


def test_is_spike_true_at_double_the_median() -> None:
    assert is_spike(200, [100, 90, 110]) is True


def test_is_spike_false_below_the_threshold() -> None:
    assert is_spike(150, [100, 90, 110]) is False


def test_is_spike_false_with_insufficient_history() -> None:
    assert is_spike(1_000_000, [100, 90]) is False


def test_is_spike_uses_the_integer_median_of_an_even_history() -> None:
    # медиана четного числа значений - целое среднее двух средних (//)
    assert is_spike(299, [100, 200, 100, 200]) is False
    assert is_spike(300, [100, 200, 100, 200]) is True


def test_parse_reading_dot_decimal() -> None:
    assert parse_reading("123.45") == 123_450


def test_parse_reading_comma_decimal() -> None:
    assert parse_reading("123,45") == 123_450


def test_parse_reading_leading_zero() -> None:
    assert parse_reading("0123") == 123_000


def test_parse_reading_garbage_returns_none() -> None:
    assert parse_reading("garbage") is None


async def test_vision_client_short_circuits_without_config() -> None:
    client = VisionClient(
        YandexConfig(api_key=None, folder_id=None),
        FilesService(make_config().files, "test-token"),
    )

    result = await client.recognize(_photo(), MeterType.COLD_WATER)

    assert result is None


async def test_vision_client_returns_none_for_a_missing_photo_file() -> None:
    # ключ и folder_id заданы, но файла на диске нет - сети клиент не касается,
    # это проверяет только сообщение об ошибке ниже по стеку (see_other test)
    client = VisionClient(
        YandexConfig(api_key="key", folder_id="folder"),
        FilesService(make_config().files, "test-token"),
    )

    result = await client.recognize(_photo(), MeterType.COLD_WATER)

    assert result is None


# ---------------------------------------------------------------------------
# Доступ
# ---------------------------------------------------------------------------


async def test_history_refuses_an_unverified_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=False)
    meter_id = await _add_meter(session, own.flat_id)
    service = _make_service(session)

    with pytest.raises(NotEnoughRights):
        await service.history(own.user_id, meter_id)


async def test_submit_refuses_an_unverified_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=False)
    meter_id = await _add_meter(session, own.flat_id)
    service = _make_service(session)

    with pytest.raises(NotEnoughRights):
        await service.submit(
            own.user_id,
            meter_id,
            SubmitDraft(
                period=_current_period(),
                values={TariffZone.SINGLE: 1_000},
                photos=[_photo()],
            ),
        )


async def test_add_meter_refuses_an_unverified_owner(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id, verified=False)
    service = _make_meters_service(session)

    with pytest.raises(NotEnoughRights):
        await service.add(
            own.user_id,
            own.flat_id,
            MeterDraft(type=MeterType.COLD_WATER, tariff_zones=1, serial="SN-1"),
        )


async def test_add_meter_refuses_a_verified_tenant(
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
        verified=True,
        can_see_charges=False,
    )
    service = _make_meters_service(session)

    with pytest.raises(NotEnoughRights):
        await service.add(
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
        verified=True,
        can_see_charges=False,
    )
    meter_id = await _add_meter(session, own.flat_id)
    await _add_tariff(session, own.house_id, ServiceType.COLD_WATER, 100_000)
    service = _make_service(session)

    result = await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=_current_period(),
            values={TariffZone.SINGLE: 1_000},
            photos=[_photo()],
        ),
    )

    assert result.row.amount is None


async def test_add_meter_allows_org_staff_of_the_managing_org(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    employee_id = await _add_user(session, "Сотрудник УК")
    await OrgsRepo(session).add_member(own.org_id, employee_id, OrgRole.EMPLOYEE)
    service = _make_meters_service(session)

    card = await service.add(
        employee_id,
        own.flat_id,
        MeterDraft(type=MeterType.COLD_WATER, tariff_zones=1, serial="SN-1"),
    )

    assert card.meter.flat_id == own.flat_id


async def test_history_refuses_a_foreign_meter_id(
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


async def test_submit_refuses_a_foreign_meter_id(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    other = await make_org_house_flat_user()
    other_meter_id = await _add_meter(session, other.flat_id)
    service = _make_service(session)

    with pytest.raises(EntityNotFound):
        await service.submit(
            own.user_id,
            other_meter_id,
            SubmitDraft(
                period=_current_period(),
                values={TariffZone.SINGLE: 1_000},
                photos=[_photo()],
            ),
        )


async def test_update_meter_refuses_a_foreign_meter_id(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    other = await make_org_house_flat_user()
    other_meter_id = await _add_meter(session, other.flat_id)
    service = _make_meters_service(session)

    with pytest.raises(EntityNotFound):
        await service.update(
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
    service = _make_admin_service(session)

    with pytest.raises(EntityNotFound):
        await service.admin_list(
            other.org_id,
            own.house_id,
            None,
            None,
            only_below_previous=False,
            limit=50,
            offset=0,
        )


# ---------------------------------------------------------------------------
# Подача показания
# ---------------------------------------------------------------------------


async def test_submit_raises_when_values_miss_a_tariff_zone(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id, tariff_zones=2)
    service = _make_service(session)

    with pytest.raises(InvalidRequest):
        await service.submit(
            own.user_id,
            meter_id,
            # у двухзонного счетчика нет ключа "night"
            SubmitDraft(
                period=_current_period(),
                values={TariffZone.DAY: 1_000},
                photos=[_photo()],
            ),
        )


async def test_submit_requires_at_least_one_photo(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    service = _make_service(session)

    with pytest.raises(InvalidRequest):
        await service.submit(
            own.user_id,
            meter_id,
            SubmitDraft(
                period=_current_period(),
                values={TariffZone.SINGLE: 1_000},
                photos=[],
            ),
        )


async def test_submit_accepts_and_flags_a_value_below_the_previous_one(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    period = _current_period()
    meters_repo = MetersRepo(session)
    await meters_repo.add_reading(
        meter_id,
        date(period.year - 1, period.month, 1),
        {TariffZone.SINGLE: 5_000},
        [_photo()],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC),
        submitted_by=own.user_id,
    )
    service = _make_service(session)

    result = await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=period,
            values={TariffZone.SINGLE: 4_000},
            photos=[_photo()],
        ),
    )

    assert result.row.reading.is_below_previous is True
    assert result.warning is not None


async def test_submit_blocks_an_expired_verification(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(
        session,
        own.flat_id,
        next_verification_date=date(2000, 1, 1),
    )
    service = _make_service(session)

    with pytest.raises(InvalidState):
        await service.submit(
            own.user_id,
            meter_id,
            SubmitDraft(
                period=_current_period(),
                values={TariffZone.SINGLE: 1_000},
                photos=[_photo()],
            ),
        )


async def test_resubmission_wins_over_the_earlier_row(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    service = _make_service(session)
    period = _current_period()

    await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=period, values={TariffZone.SINGLE: 1_000}, photos=[_photo()]
        ),
    )
    await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=period, values={TariffZone.SINGLE: 2_000}, photos=[_photo()]
        ),
    )

    history = await service.history(own.user_id, meter_id)
    assert len(history.rows) == 2

    cards = await service.list_meters(own.flat_id)
    assert len(cards) == 1
    assert cards[0].last_values == {TariffZone.SINGLE: 2_000}


async def test_submit_rejects_a_period_other_than_the_current_one_inside_the_window(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    service = _make_service(session)
    period = _current_period()
    a_year_ago = date(period.year - 1, period.month, 1)

    with pytest.raises(InvalidState):
        await service.submit(
            own.user_id,
            meter_id,
            SubmitDraft(
                period=a_year_ago, values={TariffZone.SINGLE: 1_000}, photos=[_photo()]
            ),
        )


async def test_submit_out_of_window_uses_one_of_the_allowed_past_periods(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    today = datetime.now(UTC).date()
    closed_day = _closed_window_day(today)
    await _set_window(session, own.org_id, day_from=closed_day, day_to=closed_day)
    service = _make_service(session)

    result = await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=_current_period(),
            values={TariffZone.SINGLE: 1_000},
            photos=[_photo()],
        ),
    )

    assert result.row.reading.period == _current_period()
    events = await _events(session, EventType.READING_SUBMITTED)
    assert events[-1].payload["out_of_window"] is True


async def test_submit_out_of_window_for_a_period_with_a_charge_raises(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    today = datetime.now(UTC).date()
    closed_day = _closed_window_day(today)
    await _set_window(session, own.org_id, day_from=closed_day, day_to=closed_day)
    period = _current_period()
    await _add_charge(session, own.flat_id, period)
    service = _make_service(session)

    with pytest.raises(InvalidState):
        await service.submit(
            own.user_id,
            meter_id,
            SubmitDraft(
                period=period, values={TariffZone.SINGLE: 1_000}, photos=[_photo()]
            ),
        )


async def test_submit_out_of_window_rejects_a_period_outside_periods_back(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    today = datetime.now(UTC).date()
    closed_day = _closed_window_day(today)
    await _set_window(session, own.org_id, day_from=closed_day, day_to=closed_day)
    period = _current_period()
    far_past = date(period.year - 5, period.month, 1)
    service = _make_service(session)

    with pytest.raises(InvalidState):
        await service.submit(
            own.user_id,
            meter_id,
            SubmitDraft(
                period=far_past, values={TariffZone.SINGLE: 1_000}, photos=[_photo()]
            ),
        )


async def test_submit_computes_consumption_and_the_exact_kopeck_amount(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    period = _current_period()
    meters_repo = MetersRepo(session)
    await meters_repo.add_reading(
        meter_id,
        date(period.year - 1, period.month, 1),
        {TariffZone.SINGLE: 0},
        [_photo()],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC),
        submitted_by=own.user_id,
    )
    # тариф 10.0000 руб/ед (1/10000 руб/ед): 1 единица расхода = 10 руб = 1000 коп
    await _add_tariff(session, own.house_id, ServiceType.COLD_WATER, 100_000)
    service = _make_service(session)

    result = await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=period, values={TariffZone.SINGLE: 1_000}, photos=[_photo()]
        ),
    )

    assert result.row.consumption == {TariffZone.SINGLE: 1_000}
    assert result.row.amount == 1_000


async def test_submit_records_the_reading_submitted_event(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    service = _make_service(session)

    await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=_current_period(),
            values={TariffZone.SINGLE: 1_000},
            photos=[_photo()],
            ocr_used=True,
            ocr_accepted=True,
        ),
    )

    events = await _events(session, EventType.READING_SUBMITTED)
    assert len(events) == 1
    payload = events[0].payload
    assert payload["meter_type"] == MeterType.COLD_WATER.value
    assert payload["ocr_used"] is True
    assert payload["ocr_accepted"] is True
    assert payload["is_below_previous"] is False
    assert payload["out_of_window"] is False


async def test_submit_suggests_a_leak_request_on_a_consumption_spike(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    meters_repo = MetersRepo(session)
    # 4 прошлых периода с накопительными показаниями 100, 200, 300, 400 -
    # ровный расход по 100 за каждый шаг, три дельты истории
    for back, value in zip((4, 3, 2, 1), (100, 200, 300, 400), strict=True):
        await meters_repo.add_reading(
            meter_id,
            _period_back(back),
            {TariffZone.SINGLE: value},
            [_photo()],
            ocr_used=False,
            ocr_accepted=False,
            is_below_previous=False,
            submitted_at=datetime.now(UTC),
            submitted_by=own.user_id,
        )
    service = _make_service(session)

    # расход 5000 против медианы истории 100 - многократный скачок
    result = await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=_current_period(),
            values={TariffZone.SINGLE: 5_400},
            photos=[_photo()],
        ),
    )

    assert result.suggested_category is RequestCategory.LEAK


# ---------------------------------------------------------------------------
# Начисление, счетчики, показания по дому
# ---------------------------------------------------------------------------


async def test_add_meter_rejects_a_second_meter_of_the_same_type(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    await _add_meter(session, own.flat_id)
    service = _make_meters_service(session)

    with pytest.raises(InvalidValue):
        await service.add(
            own.user_id,
            own.flat_id,
            MeterDraft(type=MeterType.COLD_WATER, tariff_zones=1, serial="SN-2"),
        )


async def test_update_meter_changes_serial_and_zones(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    service = _make_meters_service(session)

    card = await service.update(
        own.user_id,
        meter_id,
        MeterUpdateDraft(tariff_zones=2, serial="NEW-SERIAL"),
    )

    assert card.meter.tariff_zones == 2
    assert card.meter.serial == "NEW-SERIAL"


async def test_meters_repo_add_leaves_exactly_one_row_for_a_race(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    # два параллельных нажатия «добавить счетчик» бьются об уникальный индекс
    # (flat_id, type), а не об исключение из read-then-write в питоне
    own = await make_org_house_flat_user()
    meters_repo = MetersRepo(session)

    first = await meters_repo.add(own.flat_id, MeterType.COLD_WATER, 1, "SN-1", None)
    second = await meters_repo.add(own.flat_id, MeterType.COLD_WATER, 1, "SN-2", None)

    assert first is not None
    assert second is None

    stmt = (
        select(func.count())
        .select_from(meters_table)
        .where(
            meters_table.c.flat_id == own.flat_id,
            meters_table.c.type == MeterType.COLD_WATER,
        )
    )
    count = (await session.execute(stmt)).scalar_one()
    assert count == 1


async def test_house_average_covers_flats_that_submitted_for_the_same_meter_type(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)

    neighbour_user = await _add_user(session, "Сосед")
    neighbour_flat = Flat(house_id=own.house_id, number="2")
    session.add(neighbour_flat)
    await session.flush()
    await _add_resident(
        session,
        neighbour_user,
        own.house_id,
        FlatId(neighbour_flat.id),
    )
    neighbour_meter_id = await _add_meter(session, FlatId(neighbour_flat.id))

    meters_repo = MetersRepo(session)
    period = _current_period()
    for meter, user in ((meter_id, own.user_id), (neighbour_meter_id, neighbour_user)):
        # база для расчета расхода - без нее первая подача не порождает расход
        await meters_repo.add_reading(
            meter,
            _period_back(1),
            {TariffZone.SINGLE: 0},
            [_photo()],
            ocr_used=False,
            ocr_accepted=False,
            is_below_previous=False,
            submitted_at=datetime.now(UTC),
            submitted_by=user,
        )

    service = _make_service(session)

    await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=period, values={TariffZone.SINGLE: 1_000}, photos=[_photo()]
        ),
    )
    result = await service.submit(
        neighbour_user,
        neighbour_meter_id,
        SubmitDraft(
            period=period, values={TariffZone.SINGLE: 3_000}, photos=[_photo()]
        ),
    )

    # расход 1000 и 3000 относительно нулевой базы, среднее 2000
    assert result.house_average == 2_000


async def test_flats_without_reading_lists_flats_with_a_meter_and_no_submission(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_meter(session, own.flat_id)
    period = _current_period()
    meters_repo = MetersRepo(session)

    missing = await meters_repo.flats_without_reading(own.house_id, period)
    assert own.flat_id in missing

    await meters_repo.add_reading(
        await _add_meter(session, own.flat_id, meter_type=MeterType.HOT_WATER),
        period,
        {TariffZone.SINGLE: 1_000},
        [_photo()],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC),
        submitted_by=own.user_id,
    )

    still_missing = await meters_repo.flats_without_reading(own.house_id, period)
    # у квартиры теперь есть подача (пусть и другим счетчиком) - блока 18
    # интересует сам факт участия в периоде, поэтому квартиры больше нет в списке
    assert own.flat_id not in still_missing


async def test_admin_list_shows_the_whole_chain_and_the_below_previous_flag(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    # база предыдущего периода - 5000: вторая подача ниже нее, первая выше
    await MetersRepo(session).add_reading(
        meter_id,
        _period_back(1),
        {TariffZone.SINGLE: 5_000},
        [_photo()],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC),
        submitted_by=own.user_id,
    )
    service = _make_service(session)
    period = _current_period()

    await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=period, values={TariffZone.SINGLE: 6_000}, photos=[_photo()]
        ),
    )
    await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=period, values={TariffZone.SINGLE: 4_000}, photos=[_photo()]
        ),
    )
    admin_service = _make_admin_service(session)

    rows, total = await admin_service.admin_list(
        own.org_id,
        own.house_id,
        period,
        None,
        only_below_previous=False,
        limit=50,
        offset=0,
    )
    assert total == 2
    assert len(rows) == 2

    below_rows, below_total = await admin_service.admin_list(
        own.org_id,
        own.house_id,
        period,
        None,
        only_below_previous=True,
        limit=50,
        offset=0,
    )
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
        # 3 октября окно 25-5 еще сентябрьское
        (date(2026, 10, 3), _window(25, 5), date(2026, 9, 1)),
        (date(2026, 10, 1), _window(25, 1), date(2026, 9, 1)),
        (date(2027, 1, 2), _window(20, 5), date(2026, 12, 1)),
        (date(2026, 9, 20), _window(15, 25), date(2026, 9, 1)),
        (date(2026, 9, 3), None, date(2026, 9, 1)),
        # флаг «всегда открыто» хранит дни окна, но они не действуют
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
    # сегодня - последний день окна, открывшегося в прошлом месяце
    own = await make_org_house_flat_user()
    await _add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await _add_meter(session, own.flat_id)
    today = datetime.now(UTC).date()
    await _set_window(session, own.org_id, day_from=today.day + 1, day_to=today.day)
    service = _make_service(session)

    periods = await service.periods(own.flat_id)
    with pytest.raises(InvalidState, match=WRONG_PERIOD):
        await service.submit(
            own.user_id,
            meter_id,
            SubmitDraft(
                period=_current_period(),
                values={TariffZone.SINGLE: 1_000},
                photos=[_photo()],
            ),
        )
    result = await service.submit(
        own.user_id,
        meter_id,
        SubmitDraft(
            period=_period_back(1),
            values={TariffZone.SINGLE: 1_000},
            photos=[_photo()],
        ),
    )

    assert [option.period for option in periods.options] == [_period_back(1)]
    assert result.row.reading.period == _period_back(1)
