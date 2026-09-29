from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import Fixture, add_meter, add_resident, events_of, photo_name
from tests.test_readings import (
    _close_window,
    _make_service,
    _owner_with_meter,
    _period_back,
)
from tests.test_residency import _profile_service

from zheka.core.enums import EventType, MeterType, ResidentStatus, TariffZone
from zheka.core.errors import InvalidRequest
from zheka.core.ids import FlatId, MeterId
from zheka.core.services.meter_access import MeterCard
from zheka.core.services.meter_photo import (
    NOT_CONNECTED,
    NOT_VERIFIED,
    NO_HOUSE,
    NO_METERS,
    TWO_TARIFF,
    UNKNOWN_METER,
    WINDOW_CLOSED,
    MeterPhotoService,
    anomaly,
    format_volume,
    parse_volume,
)
from zheka.core.services.readings import PERIODS_BACK
from zheka.infra.database.models import Charge, Meter
from zheka.infra.database.repos.meters import MetersRepo


def _service(session: AsyncSession) -> MeterPhotoService:
    return MeterPhotoService(_profile_service(session), _make_service(session))


async def test_a_verified_flat_offers_its_single_tariff_meters(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    await MetersRepo(session).add(own.flat_id, MeterType.ELECTRICITY, 2, "SN-2", None)

    choice = await _service(session).meters(own.user_id)

    assert choice.refusal is None
    assert choice.flat_id == own.flat_id
    assert [card.meter.id for card in choice.cards] == [meter_id]
    assert choice.period is not None


@pytest.mark.parametrize(
    ("setup", "refusal"),
    [
        ("no_house", NO_HOUSE),
        ("not_connected", NOT_CONNECTED),
        ("unverified", NOT_VERIFIED),
        ("blocked", NOT_VERIFIED),
        ("two_tariff", TWO_TARIFF),
        ("expired", NO_METERS),
        ("no_meters", NO_METERS),
        ("window_closed", WINDOW_CLOSED),
    ],
)
async def test_a_photo_is_refused_with_its_reason(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    setup: str,
    refusal: str,
) -> None:
    own = await make_org_house_flat_user(registered=setup != "not_connected")
    if setup != "no_house":
        await add_resident(
            session,
            own.user_id,
            own.house_id,
            own.flat_id,
            verified=setup != "unverified",
            status=(
                ResidentStatus.BLOCKED if setup == "blocked" else ResidentStatus.ACTIVE
            ),
        )
    if setup in {"blocked", "window_closed"}:
        await add_meter(session, own.flat_id)
    if setup == "two_tariff":
        await add_meter(session, own.flat_id, tariff_zones=2)
    if setup == "expired":
        await add_meter(
            session,
            own.flat_id,
            next_verification_date=_period_back(1),
        )
    if setup == "window_closed":
        await _close_window(session, own.org_id)
        for months_back in range(PERIODS_BACK):
            session.add(
                Charge(
                    flat_id=own.flat_id,
                    period=_period_back(months_back),
                    lines={},
                    total=0,
                    is_closed=True,
                ),
            )
        await session.flush()

    choice = await _service(session).meters(own.user_id)

    assert choice.refusal == refusal
    assert choice.cards == ()


async def test_a_bot_reading_is_submitted_with_its_channel_and_ocr_marks(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, meter_id = await _owner_with_meter(session, make_org_house_flat_user)
    service = _service(session)
    choice = await service.meters(own.user_id)
    assert choice.period is not None

    await service.submit(
        own.user_id,
        meter_id,
        choice.period,
        1_500,
        photo_name(),
        recognized=1_000,
    )

    [event] = await events_of(session, EventType.READING_SUBMITTED)
    assert event.payload["channel"] == "bot"
    assert (event.payload["ocr_used"], event.payload["ocr_accepted"]) == (True, False)


async def test_a_meter_of_another_flat_is_not_submitted(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, _ = await _owner_with_meter(session, make_org_house_flat_user)
    _, foreign = await _owner_with_meter(session, make_org_house_flat_user)
    service = _service(session)

    with pytest.raises(InvalidRequest):
        await service.card(own.user_id, foreign)


def _card(last: int | None, period: date | None) -> MeterCard:
    return MeterCard(
        meter=Meter(
            id=MeterId(1),
            flat_id=FlatId(1),
            type=MeterType.COLD_WATER,
            serial="1",
        ),
        can_submit=True,
        verification_expired=False,
        last_period=period,
        last_values=None if last is None else {TariffZone.SINGLE: last},
        prior_period=None,
        prior_values=None,
    )


@pytest.mark.parametrize(
    ("value", "kind"),
    [(9_000, "below"), (60_000, None), (61_000, "high"), (120_000, "high")],
)
def test_an_implausible_reading_is_flagged_like_in_the_app(
    value: int,
    kind: str | None,
) -> None:
    card = _card(10_000, date(2026, 8, 1))

    assert anomaly(card, date(2026, 9, 1), value) == kind
    assert anomaly(_card(None, None), date(2026, 9, 1), value) is None


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("123", 123_000),
        ("123,4", 123_400),
        (" 1 234.567 ", 1_234_567),
        ("12,3456", None),
        ("abc", None),
        ("", None),
    ],
)
def test_a_typed_reading_is_parsed_to_thousandths(text: str, value: int | None) -> None:
    assert parse_volume(text) == value


def test_a_volume_prints_with_three_decimals() -> None:
    assert format_volume(3_356) == "3,356"
    assert format_volume(-50) == "-0,050"


async def test_a_two_tariff_meter_is_not_submitted_from_a_photo(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own, _ = await _owner_with_meter(session, make_org_house_flat_user)
    meter = await MetersRepo(session).add(
        own.flat_id,
        MeterType.ELECTRICITY,
        2,
        "E",
        None,
    )
    assert meter is not None
    service = _service(session)
    choice = await service.meters(own.user_id)
    assert choice.period is not None

    with pytest.raises(InvalidRequest, match=UNKNOWN_METER):
        await service.submit(
            own.user_id,
            meter.id,
            choice.period,
            1_000,
            photo_name(),
            recognized=None,
        )
