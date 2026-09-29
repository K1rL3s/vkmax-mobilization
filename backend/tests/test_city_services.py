from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser
from tests.test_houses import _make_service

from zheka.api.schemas.houses import HouseCard
from zheka.core.city_services import city_services, directory
from zheka.core.enums import CityServiceKind
from zheka.infra.database.models import House
from zheka.infra.database.tables.houses import houses_table

TATARSTAN = "Республика Татарстан"


def test_every_row_names_its_official_source() -> None:
    assert directory()
    for service in directory():
        assert service.phone
        assert service.source_url.startswith("https://")
        assert service.site is None or service.site.startswith("https://")


def test_a_kazan_house_gets_every_kind_of_service() -> None:
    kinds = [service.kind for service in city_services(TATARSTAN, "Казань")]

    assert kinds == list(CityServiceKind)


def test_another_city_of_the_region_gets_only_the_region_wide_inspection() -> None:
    services = city_services(TATARSTAN, "Набережные Челны")

    assert [service.kind for service in services] == [CityServiceKind.GZHI]


def test_a_city_from_another_region_gets_nothing() -> None:
    assert city_services("Тестовая область", "Казань") == []


async def test_the_house_card_lists_the_city_services(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    stmt = (
        update(House)
        .where(houses_table.c.id == own.house_id)
        .values(region="Санкт-Петербург", city="Санкт-Петербург")
    )
    await session.execute(stmt)
    session.expire_all()

    data = await _make_service(session).house_card(
        own.house_id,
        own.user_id,
        datetime.now(UTC),
    )
    card = HouseCard.of(data, [])

    water = next(item for item in card.services if item.kind is CityServiceKind.WATER)
    assert water.name == "ГУП «Водоканал Санкт-Петербурга»"
    assert water.phone == "+7 (812) 305-09-09"
    assert [item.kind for item in card.services] == list(CityServiceKind)
