from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser
from tests.test_houses import _make_service

from zheka.api.schemas.houses import HouseCard
from zheka.core.ids import HouseId
from zheka.core.models import House
from zheka.core.outages import DEMO_COMPANY, HINT_NOTE, demo_outages

MORNING = datetime(2026, 9, 30, 5, tzinfo=UTC)


def _house(house_id: int) -> House:
    return House(
        id=HouseId(house_id),
        region="Москва",
        city="Москва",
        street="Тестовая",
        building="1",
        chat_binding_code="abcd1234",
        timezone="Europe/Moscow",
    )


def test_every_house_gets_the_same_demo_outages_within_a_day() -> None:
    for house_id in range(1, 40):
        house = _house(house_id)

        first = demo_outages(house, MORNING)

        assert len(first) == 2
        assert first == demo_outages(house, MORNING + timedelta(hours=1))
        assert first[0].resource != first[1].resource
        assert all(item.is_demo and item.company == DEMO_COMPANY for item in first)
        assert all(item.recalc_hint.endswith(HINT_NOTE) for item in first)
        assert all(item.starts_at < item.ends_at for item in first)


def test_an_ended_outage_drops_out() -> None:
    house = _house(7)
    today, planned = demo_outages(house, MORNING)

    later = demo_outages(house, today.ends_at + timedelta(minutes=1))

    assert later == [planned]


async def test_the_house_card_shows_the_outages(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    data = await _make_service(session).house_card(
        own.house_id,
        own.user_id,
        datetime.now(UTC),
    )

    card = HouseCard.of(data, [])

    assert card.outages
    assert all(item.is_demo for item in card.outages)
