import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser

from zheka.core.enums import EventSource, OrgRole, ResidentRole
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import FlatId, HouseId, OrgId, UserId
from zheka.core.services.events import EventsService
from zheka.core.services.houses import HousesService
from zheka.infra.database.models import Flat, House
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.residents import demand_signals_table, residents_table


def _make_service(session: AsyncSession) -> HousesService:
    return HousesService(
        HousesRepo(session),
        ResidentsRepo(session),
        OrgsRepo(session),
        UsersRepo(session),
        FlatsRepo(session),
        EventsService(EventsRepo(session)),
    )


async def _consent(session: AsyncSession, fixture: OrgHouseFlatUser) -> None:
    user = await UsersRepo(session).get_by_id(fixture.user_id)
    assert user is not None
    user.consent_at = datetime.now(UTC)
    await session.flush()


async def _count_residencies(session: AsyncSession, user_id: UserId) -> int:
    stmt = (
        select(func.count())
        .select_from(residents_table)
        .where(residents_table.c.user_id == user_id)
    )
    return (await session.execute(stmt)).scalar_one()


async def _count_demand_rows(session: AsyncSession, house_id: HouseId) -> int:
    stmt = (
        select(func.count())
        .select_from(demand_signals_table)
        .where(demand_signals_table.c.house_id == house_id)
    )
    return (await session.execute(stmt)).scalar_one()


async def test_link_refuses_without_consent(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()

    with pytest.raises(NotEnoughRights):
        await _make_service(session).link(
            fixture.user_id,
            fixture.house_id,
            None,
            ResidentRole.OWNER,
            EventSource.MINIAPP,
            None,
        )

    assert await _count_residencies(session, fixture.user_id) == 0


async def test_link_twice_returns_the_same_residency(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    await _consent(session, fixture)
    service = _make_service(session)

    first = await service.link(
        fixture.user_id,
        fixture.house_id,
        fixture.flat_id,
        ResidentRole.TENANT,
        EventSource.MINIAPP,
        None,
    )
    # значение снимается до второй привязки: обе вьюхи держат один и тот же
    # объект жителя, и после обновления роли first показал бы уже новые флаги
    tenant_can_vote = first.resident.can_vote
    second = await service.link(
        fixture.user_id,
        fixture.house_id,
        fixture.flat_id,
        ResidentRole.OWNER,
        EventSource.QR,
        None,
    )

    assert second.resident.id == first.resident.id
    assert await _count_residencies(session, fixture.user_id) == 1
    # роль и производные от нее флаги обновляются, иначе вошедший однажды
    # арендатором навсегда остался бы без начислений и голоса
    assert (tenant_can_vote, second.resident.can_vote) == (False, True)
    assert second.resident.can_see_charges is True


async def test_demand_signal_counts_a_user_once(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    # дом без подключенной УК: сид заводит дом с org_id, а кнопка спроса
    # живет только там, где организации нет
    fixture = await make_org_house_flat_user()
    house = await HousesRepo(session).get(fixture.house_id)
    assert house is not None
    house.org_id = None
    await session.flush()
    service = _make_service(session)

    first = await service.demand_signal(fixture.user_id, fixture.house_id)
    second = await service.demand_signal(fixture.user_id, fixture.house_id)

    assert (first, second) == (1, 1)
    assert await _count_demand_rows(session, fixture.house_id) == 1

    # карточка обязана показать, что кнопку жал именно этот житель, иначе
    # фронт нарисует ее ненажатой и повторное нажатие выглядит поломкой
    card = await service.house_card(fixture.house_id, fixture.user_id)
    assert (card.demand_count, card.demand_sent) == (1, True)


async def _add_house(
    session: AsyncSession,
    org_id: OrgId,
    lat: Decimal,
    lon: Decimal,
) -> HouseId:
    house = House(
        org_id=org_id,
        region="Тестовая область",
        city="Тестоград",
        street="Тестовая",
        building=secrets.token_hex(2),
        cadastral_no=secrets.token_hex(8),
        chat_binding_code=secrets.token_hex(4),
        lat=lat,
        lon=lon,
    )
    session.add(house)
    await session.flush()
    return HouseId(house.id)


async def _add_address(
    session: AsyncSession,
    org_id: OrgId,
    city: str,
    street: str,
    building: str,
) -> HouseId:
    house = House(
        org_id=org_id,
        region="Республика Татарстан",
        city=city,
        street=street,
        building=building,
        cadastral_no=secrets.token_hex(8),
        chat_binding_code=secrets.token_hex(4),
    )
    session.add(house)
    await session.flush()
    return HouseId(house.id)


async def test_search_by_query_ignores_word_order_and_case(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    # в макете одно поле поиска: адрес житель набирает как придется, и города
    # в строке может не быть вовсе
    fixture = await make_org_house_flat_user()
    wanted = await _add_address(session, fixture.org_id, "Казань", "Баумана", "12")
    await _add_address(session, fixture.org_id, "Казань", "Кремлевская", "12")
    await _add_address(session, fixture.org_id, "Москва", "Баумана", "3")
    service = _make_service(session)

    for query in ("Баумана 12", "12 баумана", "  БАУМАНА   12 ", "казань баумана 12"):
        found, total = await service.search(
            fixture.user_id,
            None,
            None,
            None,
            query,
            20,
            0,
        )
        assert [item.house.id for item in found] == [wanted], query
        assert total == 1


async def test_search_by_city_keeps_working(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    wanted = await _add_address(session, fixture.org_id, "Казань", "Баумана", "12")
    await _add_address(session, fixture.org_id, "Москва", "Баумана", "12")

    found, total = await _make_service(session).search(
        fixture.user_id,
        "Казань",
        "Баумана",
        "12",
        None,
        20,
        0,
    )

    assert [item.house.id for item in found] == [wanted]
    assert total == 1


@pytest.mark.parametrize("blank", [None, "", "   "])
async def test_search_without_city_and_query_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
    blank: str | None,
) -> None:
    fixture = await make_org_house_flat_user()

    with pytest.raises(InvalidRequest):
        await _make_service(session).search(
            fixture.user_id,
            blank,
            None,
            None,
            blank,
            20,
            0,
        )


async def test_nearby_measures_longitude_in_metres_not_in_degrees(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    # градус долготы на широте Москвы почти вдвое короче градуса широты:
    # без множителя cos(широты) дом в 200 метрах к востоку выглядит как 356,
    # выпадает из радиуса 250 и стоит в выдаче ниже дома в 200 метрах к северу
    lat, lon = Decimal("55.751244"), Decimal("37.618423")
    north = Decimal("0.001797")  # 200 метров по меридиану
    east = Decimal("0.003195")  # 200 метров по параллели на этой широте
    fixture = await make_org_house_flat_user()

    north_id = await _add_house(session, fixture.org_id, lat + north, lon)
    east_id = await _add_house(session, fixture.org_id, lat, lon + east)

    found = await _make_service(session).nearest(
        fixture.user_id,
        float(lat),
        float(lon),
        250,
        20,
    )

    distances = {item.house.id: item.distance_m for item in found}
    assert distances.keys() == {north_id, east_id}
    assert distances[north_id] == pytest.approx(200, abs=10)
    assert distances[east_id] == pytest.approx(200, abs=10)

    # радиус из запроса доходит до базы целиком: потолка в сервисе нет
    far_id = await _add_house(session, fixture.org_id, lat + north * 10, lon)
    far = await _make_service(session).nearest(
        fixture.user_id,
        float(lat),
        float(lon),
        5000,
        20,
    )
    assert far_id in {item.house.id for item in far}


async def test_link_with_another_flat_refuses_to_move_the_residency(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    await _consent(session, fixture)
    other_flat = Flat(house_id=fixture.house_id, number="2")
    session.add(other_flat)
    await session.flush()
    service = _make_service(session)

    first = await service.link(
        fixture.user_id,
        fixture.house_id,
        fixture.flat_id,
        ResidentRole.OWNER,
        EventSource.MINIAPP,
        None,
    )

    with pytest.raises(InvalidState):
        await service.link(
            fixture.user_id,
            fixture.house_id,
            FlatId(other_flat.id),
            ResidentRole.OWNER,
            EventSource.MINIAPP,
            None,
        )

    again = await service.link(
        fixture.user_id,
        fixture.house_id,
        fixture.flat_id,
        ResidentRole.OWNER,
        EventSource.MINIAPP,
        None,
    )
    assert again.resident.id == first.resident.id


async def test_link_gives_a_flat_to_a_residency_that_had_none(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    # диплинк из домового чата привязывает к дому, не зная квартиры, а она
    # выбирается на отдельном экране уже после - этот путь не должен упираться
    # в отказ, предназначенный для переселения
    fixture = await make_org_house_flat_user()
    await _consent(session, fixture)
    service = _make_service(session)

    first = await service.link(
        fixture.user_id,
        fixture.house_id,
        None,
        ResidentRole.OWNER,
        EventSource.CHAT,
        None,
    )
    assert first.resident.flat_id is None

    second = await service.link(
        fixture.user_id,
        fixture.house_id,
        fixture.flat_id,
        ResidentRole.OWNER,
        EventSource.MINIAPP,
        None,
    )

    assert second.resident.id == first.resident.id
    assert second.resident.flat_id == fixture.flat_id
    assert second.flat is not None


async def test_admin_house_surface(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user(
        org_role=OrgRole.CREATOR,
        resident_role=ResidentRole.OWNER,
    )
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    houses_service = _make_service(session)

    rows, total = await houses_service.org_houses(own.org_id, None, 50, 0)
    assert total == 1
    assert rows[0].flats_count == 1
    assert rows[0].residents_count == 1
    assert rows[0].open_requests == 0
    assert rows[0].chat_bound is False

    card = await houses_service.admin_card(own.org_id, own.house_id)
    assert card.verified_residents_count == 0
    assert card.pending_verifications == 0
    assert card.chairman_name is None

    residents, total = await houses_service.house_residents(
        own.org_id,
        own.house_id,
        "Тест",
        50,
        0,
    )
    assert total == 1
    assert residents[0].flat is not None

    old_code = card.house.chat_binding_code
    house = await houses_service.rotate_binding_code(own.org_id, own.house_id)
    assert house.chat_binding_code != old_code

    with pytest.raises(EntityNotFound):
        await houses_service.admin_card(own.org_id, other.house_id)
