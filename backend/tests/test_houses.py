import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import Column, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser

from zheka.api.schemas.houses import ResidencySummary
from zheka.core.enums import ChatStatus, EventSource, OrgRole, ResidentRole
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import FlatId, HouseId, MaxChatId, OrgId
from zheka.core.services.events import EventsService
from zheka.core.services.houses import HousesService, ResidencyView
from zheka.infra.database.models import Chat, Flat, House
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


async def _link(
    session: AsyncSession,
    fixture: OrgHouseFlatUser,
    flat_id: FlatId | None = None,
    number: str | None = None,
    role: ResidentRole = ResidentRole.OWNER,
) -> ResidencyView:
    return await _make_service(session).link(
        fixture.user_id,
        fixture.house_id,
        flat_id,
        number,
        role,
        EventSource.MINIAPP,
        None,
    )


async def _consent(session: AsyncSession, fixture: OrgHouseFlatUser) -> None:
    user = await UsersRepo(session).get_by_id(fixture.user_id)
    assert user is not None
    user.consent_at = datetime.now(UTC)
    await session.flush()


async def _count(session: AsyncSession, column: Column[int], value: int) -> int:
    stmt = select(func.count()).where(column == value)
    return (await session.execute(stmt)).scalar_one()


async def _add_house(session: AsyncSession, org_id: OrgId, **fields: Any) -> HouseId:
    house = House(
        timezone="Europe/Moscow",
        **{
            "org_id": org_id,
            "region": "Тестовая область",
            "city": "Тестоград",
            "street": "Тестовая",
            "building": secrets.token_hex(2),
            "cadastral_no": secrets.token_hex(8),
            "chat_binding_code": secrets.token_hex(4),
            **fields,
        },
    )
    session.add(house)
    await session.flush()
    return house.id


async def test_link_refuses_without_consent(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()

    with pytest.raises(NotEnoughRights):
        await _link(session, fixture)

    assert await _count(session, residents_table.c.user_id, fixture.user_id) == 0


async def test_link_twice_returns_the_same_residency(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    await _consent(session, fixture)

    first = await _link(session, fixture, fixture.flat_id, role=ResidentRole.TENANT)
    # обе вьюхи держат один объект жителя, поэтому флаг снимается до второй
    tenant_can_vote = first.resident.can_vote
    second = await _link(session, fixture, fixture.flat_id)

    assert second.resident.id == first.resident.id
    assert await _count(session, residents_table.c.user_id, fixture.user_id) == 1
    # роль и флаги обновляются, иначе вошедший арендатором остался бы им навсегда
    assert (tenant_can_vote, second.resident.can_vote) == (False, True)
    assert second.resident.can_see_charges is True


async def test_demand_signal_counts_a_user_once(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    # кнопка спроса живет только у дома без УК
    fixture = await make_org_house_flat_user()
    house = await HousesRepo(session).get(fixture.house_id)
    assert house is not None
    house.org_id = None
    await session.flush()
    service = _make_service(session)

    first = await service.demand_signal(fixture.user_id, fixture.house_id)
    second = await service.demand_signal(fixture.user_id, fixture.house_id)

    assert (first, second) == (1, 1)
    assert await _count(session, demand_signals_table.c.house_id, house.id) == 1
    card = await service.house_card(fixture.house_id, fixture.user_id)
    assert (card.demand_count, card.demand_sent) == (1, True)


async def test_search_by_query_or_by_address_parts(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    wanted = await _add_house(
        session, fixture.org_id, city="Казань", street="Баумана", building="12"
    )
    await _add_house(
        session, fixture.org_id, city="Казань", street="Кремлевская", building="12"
    )
    await _add_house(
        session, fixture.org_id, city="Москва", street="Баумана", building="3"
    )
    service = _make_service(session)

    for query in ("Баумана 12", "12 баумана", "  БАУМАНА   12 ", "казань баумана 12"):
        found, total = await service.search(
            fixture.user_id, None, None, None, query, 20, 0
        )
        assert [item.house.id for item in found] == [wanted], query
        assert total == 1

    found, total = await service.search(
        fixture.user_id, "Казань", "Баумана", None, None, 20, 0
    )
    assert [item.house.id for item in found] == [wanted]
    assert total == 1


@pytest.mark.parametrize("blank", [None, "   "])
async def test_search_without_city_and_query_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
    blank: str | None,
) -> None:
    fixture = await make_org_house_flat_user()

    with pytest.raises(InvalidRequest):
        await _make_service(session).search(
            fixture.user_id, blank, None, None, blank, 20, 0
        )


async def test_nearby_measures_longitude_in_metres_not_in_degrees(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    # без множителя cos(широты) дом в 200 метрах к востоку выглядит как 356
    # и выпадает из радиуса 250
    lat, lon = Decimal("55.751244"), Decimal("37.618423")
    north = Decimal("0.001797")  # 200 метров по меридиану
    east = Decimal("0.003195")  # 200 метров по параллели на этой широте
    fixture = await make_org_house_flat_user()

    north_id = await _add_house(session, fixture.org_id, lat=lat + north, lon=lon)
    east_id = await _add_house(session, fixture.org_id, lat=lat, lon=lon + east)

    found = await _make_service(session).nearest(
        fixture.user_id, float(lat), float(lon), 250, 20
    )

    distances = {item.house.id: item.distance_m for item in found}
    assert distances.keys() == {north_id, east_id}
    assert distances[north_id] == pytest.approx(200, abs=10)
    assert distances[east_id] == pytest.approx(200, abs=10)

    # радиус из запроса доходит до базы целиком: потолка в сервисе нет
    far_id = await _add_house(session, fixture.org_id, lat=lat + north * 10, lon=lon)
    far = await _make_service(session).nearest(
        fixture.user_id, float(lat), float(lon), 5000, 20
    )
    assert far_id in {item.house.id for item in far}


async def test_link_moves_an_unverified_residency_to_another_flat(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    # опечатка в номере не должна запирать жителя в чужой квартире
    fixture = await make_org_house_flat_user()
    await _consent(session, fixture)
    other_flat = Flat(house_id=fixture.house_id, number="2")
    session.add(other_flat)
    await session.flush()

    first = await _link(session, fixture, fixture.flat_id)
    moved = await _link(session, fixture, other_flat.id)

    assert moved.resident.id == first.resident.id
    assert moved.resident.flat_id == other_flat.id
    assert await _count(session, residents_table.c.user_id, fixture.user_id) == 1

    by_number = await _link(session, fixture, number="77")
    assert (by_number.resident.flat_id, by_number.resident.flat_number) == (None, "77")
    summary = ResidencySummary.of(by_number)
    assert (summary.flat_id, summary.flat_number) == (None, "77")


async def test_link_refuses_to_move_a_verified_residency(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    await _consent(session, fixture)
    other_flat = Flat(house_id=fixture.house_id, number="2")
    session.add(other_flat)
    await session.flush()

    first = await _link(session, fixture, fixture.flat_id)
    first.resident.verified_at = datetime.now(UTC)
    await session.flush()

    with pytest.raises(InvalidState):
        await _link(session, fixture, other_flat.id)
    with pytest.raises(InvalidState):
        await _link(session, fixture, number="77")

    again = await _link(session, fixture, fixture.flat_id)
    assert again.resident.id == first.resident.id
    assert again.resident.flat_id == fixture.flat_id


async def test_link_by_the_number_of_a_known_flat_takes_that_flat(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    await _consent(session, fixture)

    view = await _link(session, fixture, number=" 1 ")

    assert view.resident.flat_id == fixture.flat_id
    assert view.resident.flat_number is None
    summary = ResidencySummary.of(view)
    assert (summary.flat_id, summary.flat_number) == (fixture.flat_id, "1")


async def test_link_refuses_a_flat_id_together_with_a_number(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    await _consent(session, fixture)

    with pytest.raises(InvalidRequest):
        await _link(session, fixture, fixture.flat_id, "1")

    assert await _count(session, residents_table.c.user_id, fixture.user_id) == 0


async def test_admin_house_surface(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user(
        org_role=OrgRole.CREATOR, resident_role=ResidentRole.OWNER
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
        own.org_id, own.house_id, "Тест", 50, 0
    )
    assert total == 1
    assert residents[0].flat is not None

    old_code = card.house.chat_binding_code
    house = await houses_service.rotate_binding_code(own.org_id, own.house_id)
    assert house.chat_binding_code != old_code

    with pytest.raises(EntityNotFound):
        await houses_service.admin_card(own.org_id, other.house_id)


async def test_flats_are_listed_to_a_resident_and_hidden_from_a_stranger(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    stranger = await make_org_house_flat_user()
    free_flat = Flat(house_id=own.house_id, number="2")
    session.add(free_flat)
    await session.flush()
    service = _make_service(session)

    flats, total, taken = await service.flats(
        own.user_id, own.house_id, None, None, 50, 0
    )

    assert total == 2
    assert {flat.id for flat in flats} == {own.flat_id, free_flat.id}
    assert taken == {own.flat_id}
    # is_taken выдает, где живут наши пользователи: чужой дом отвечает 404
    with pytest.raises(EntityNotFound):
        await service.flats(stranger.user_id, own.house_id, None, None, 50, 0)


async def test_a_chat_the_bot_was_removed_from_is_not_bound(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    # удаленный из чата бот оставляет bound_at, а написать туда уже нельзя
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    session.add(
        Chat(
            chat_id=MaxChatId(secrets.randbits(48)),
            house_id=data.house_id,
            title="Дом",
            bound_at=datetime.now(UTC),
            status=ChatStatus.REMOVED,
        )
    )
    await session.flush()
    repo = HousesRepo(session)

    assert await repo.is_chat_bound(data.house_id) is False
    assert await repo.bound_chat_titles([data.house_id]) == {}
