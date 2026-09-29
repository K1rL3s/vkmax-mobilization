import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from maxo.dialogs.test_tools.bot_client import FakeBot
from maxo.utils.deeplink import create_startapp_link
from sqlalchemy import Column, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser, add_user

from zheka.api.routes.admin.houses import object_qrs
from zheka.api.schemas.houses import (
    AdminHouseCard,
    AdminHouseListItem,
    EntranceQr,
    HouseCard,
    ResidencySummary,
)
from zheka.core.consent import CONSENT_VERSION
from zheka.core.deeplinks import OBJECT_QR_CATEGORIES
from zheka.core.enums import (
    ChatStatus,
    EventSource,
    OrgRole,
    RequestCategory,
    RequestChannel,
    RequestStatus,
    ResidentRole,
    ResidentStatus,
)
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import FlatId, HouseId, MaxChatId, OrgId
from zheka.core.services.events import EventsService
from zheka.core.services.houses import HousesService, ResidencyView
from zheka.infra.database.models import Chat, Flat, House, Request, Resident
from zheka.infra.database.repos.analytics import AnalyticsRepo
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
        AnalyticsRepo(session),
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
    await UsersRepo(session).set_consent(fixture.user_id, CONSENT_VERSION)


async def _make_chairman(session: AsyncSession, fixture: OrgHouseFlatUser) -> None:
    resident = await ResidentsRepo(session).get_for_house(
        fixture.user_id,
        fixture.house_id,
    )
    assert resident is not None
    resident.is_chairman = True
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
    tenant_can_vote = first.resident.can_vote
    second = await _link(session, fixture, fixture.flat_id)

    assert second.resident.id == first.resident.id
    assert await _count(session, residents_table.c.user_id, fixture.user_id) == 1
    assert (tenant_can_vote, second.resident.can_vote) == (False, True)
    assert second.resident.can_see_charges is True


async def test_demand_signal_counts_a_user_once(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
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
    card = HouseCard.of(
        await service.house_card(
            fixture.house_id,
            fixture.user_id,
            datetime.now(UTC),
        ),
        [],
    )
    assert (card.demand_count, card.demand_sent, card.org) == (1, True, None)


async def test_search_by_query_or_by_address_parts(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    wanted = await _add_house(
        session,
        fixture.org_id,
        city="Казань",
        street="Баумана",
        building="12",
    )
    await _add_house(
        session,
        fixture.org_id,
        city="Казань",
        street="Кремлевская",
        building="12",
    )
    await _add_house(
        session,
        fixture.org_id,
        city="Москва",
        street="Баумана",
        building="3",
    )
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

    found, total = await service.search(
        fixture.user_id,
        "Казань",
        "Баумана",
        None,
        None,
        20,
        0,
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
    lat, lon = Decimal("55.751244"), Decimal("37.618423")
    north = Decimal("0.001797")
    east = Decimal("0.003195")
    fixture = await make_org_house_flat_user()

    north_id = await _add_house(session, fixture.org_id, lat=lat + north, lon=lon)
    east_id = await _add_house(session, fixture.org_id, lat=lat, lon=lon + east)
    far_id = await _add_house(session, fixture.org_id, lat=lat + north * 10, lon=lon)

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

    far = await _make_service(session).nearest(
        fixture.user_id,
        float(lat),
        float(lon),
        5000,
        20,
    )
    assert far_id in {item.house.id for item in far}


async def test_link_moves_an_unverified_residency_to_another_flat(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
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
        org_role=OrgRole.CREATOR,
        resident_role=ResidentRole.OWNER,
    )
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    session.add(Flat(house_id=own.house_id, number="2"))
    session.add(
        Request(
            house_id=own.house_id,
            flat_id=own.flat_id,
            author_user_id=own.user_id,
            category=RequestCategory.LEAK,
            description="Течет",
            status=RequestStatus.NEW,
            channel=RequestChannel.MINIAPP,
            deadline_at=datetime.now(UTC),
        ),
    )
    await _make_chairman(session, own)
    houses_service = _make_service(session)

    rows, total = await houses_service.org_houses(own.org_id, None, 50, 0)
    assert total == 1
    item = AdminHouseListItem.of(rows[0], can_manage=True)
    assert (item.id, item.flats_count, item.residents_count) == (own.house_id, 2, 1)
    assert (item.open_requests, item.chat_bound) == (1, False)

    card = await houses_service.admin_card(own.org_id, own.house_id)
    qrs = [EntranceQr(entrance=1, code="qr", deeplink="https://max.ru/qr")]
    admin = AdminHouseCard.of(card, qrs)
    assert (admin.flats_count, admin.residents_count, admin.open_requests) == (2, 1, 1)
    assert (admin.verified_residents_count, admin.pending_verifications) == (0, 0)
    assert (admin.chairman_name, admin.entrance_qrs) == ("Тест Тестов", qrs)
    assert admin.chat_binding_code == card.house.chat_binding_code

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


async def test_flats_are_listed_to_anyone_and_taken_only_to_a_resident(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    stranger = await make_org_house_flat_user()
    blocked = await make_org_house_flat_user()
    free_flat = Flat(house_id=own.house_id, number="2")
    session.add_all(
        [
            free_flat,
            Resident(
                user_id=blocked.user_id,
                house_id=own.house_id,
                role=ResidentRole.TENANT,
                status=ResidentStatus.BLOCKED,
            ),
        ],
    )
    await session.flush()
    service = _make_service(session)

    flats, total, taken = await service.flats(
        own.user_id,
        own.house_id,
        None,
        None,
        50,
        0,
    )

    assert total == 2
    assert {flat.id for flat in flats} == {own.flat_id, free_flat.id}
    assert taken == {own.flat_id}
    for outsider in (stranger, blocked):
        flats, total, taken = await service.flats(
            outsider.user_id,
            own.house_id,
            None,
            None,
            50,
            0,
        )
        assert total == 2
        assert {flat.id for flat in flats} == {own.flat_id, free_flat.id}
        assert taken == set()
    with pytest.raises(EntityNotFound):
        await service.flats(stranger.user_id, HouseId(0), None, None, 50, 0)


async def test_a_chat_the_bot_was_removed_from_is_not_bound(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    session.add(
        Chat(
            chat_id=MaxChatId(secrets.randbits(48)),
            house_id=data.house_id,
            title="Дом",
            bound_at=datetime.now(UTC),
            status=ChatStatus.REMOVED,
        ),
    )
    await session.flush()
    repo = HousesRepo(session)

    assert await repo.is_chat_bound(data.house_id) is False
    assert await repo.bound_chat_titles([data.house_id]) == {}


async def test_house_flats_are_ordered_as_numbers_before_the_limit(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    house_id = await _add_house(session, fixture.org_id)
    session.add_all(
        [Flat(house_id=house_id, number=number) for number in ("10", "2", "1")],
    )
    await session.flush()

    flats = await _make_service(session).house_flats(house_id, 2)

    assert [flat.number for flat in flats] == ["1", "2"]


async def test_a_wildcard_in_a_search_is_a_plain_character(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    region = f"Область {secrets.token_hex(4)}"
    city = f"Город {secrets.token_hex(4)}"
    await _add_house(session, fixture.org_id, region=region, city=city)
    houses = HousesRepo(session)

    assert await houses.list_cities(region, "%") == []
    assert await houses.list_streets(city, None, "%") == []
    assert (await houses.search(city, None, "%", None, 50, 0))[1] == 0
    assert (await houses.search(None, None, None, "%", 50, 0))[1] == 0
    assert (await houses.list_flats(fixture.house_id, "%", None, 50, 0))[1] == 0
    assert (await houses.search_for_org(fixture.org_id, "%", 50, 0))[1] == 0
    residents = ResidentsRepo(session)
    assert (await residents.search_for_house(fixture.house_id, "%", 50, 0))[1] == 0


async def test_house_card_gives_the_binding_code_to_the_chairman_alone(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    stranger = await add_user(session)
    house = await HousesRepo(session).get(own.house_id)
    assert house is not None
    house.lat = Decimal("55.751244")
    await _make_chairman(session, own)
    service = _make_service(session)

    card = HouseCard.of(
        await service.house_card(own.house_id, own.user_id, datetime.now(UTC)),
        [],
    )
    seen = HouseCard.of(
        await service.house_card(own.house_id, stranger, datetime.now(UTC)),
        [],
    )

    assert card.chat_binding_code == house.chat_binding_code
    assert card.lat == 55.751244
    assert card.org is not None
    assert card.org.id == own.org_id
    assert card.my_residency is not None
    assert card.my_residency.flat_id == own.flat_id
    assert (seen.chat_binding_code, seen.my_residency) == (None, None)


async def test_a_blocked_resident_cannot_unlink_to_shed_the_block(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    residents = ResidentsRepo(session)
    resident = await residents.get_for_house(own.user_id, own.house_id)
    assert resident is not None
    await residents.set_status(resident, ResidentStatus.BLOCKED, "Задолженность")

    with pytest.raises(NotEnoughRights):
        await _make_service(session).unlink(own.user_id, resident.id)

    assert await residents.get(resident.id) is not None


async def test_a_verified_tenant_cannot_relink_as_the_owner(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    await _consent(session, fixture)
    first = await _link(session, fixture, fixture.flat_id, role=ResidentRole.TENANT)
    first.resident.verified_at = datetime.now(UTC)
    await session.flush()

    with pytest.raises(InvalidState):
        await _link(session, fixture, fixture.flat_id)
    with pytest.raises(InvalidState):
        await _link(session, fixture)

    again = await _link(session, fixture, fixture.flat_id, role=ResidentRole.TENANT)
    assert again.resident.role is ResidentRole.TENANT
    assert again.resident.can_see_charges is False


async def _closed(
    session: AsyncSession,
    house_id: HouseId,
    now: datetime,
    *,
    days_ago: int = 2,
    late: bool = False,
    accepted_after: int | None = None,
    rating: int | None = None,
) -> None:
    created_at = now - timedelta(days=days_ago)
    deadline_at = created_at + timedelta(days=1)
    reviewed_at = deadline_at + timedelta(hours=1) if late else deadline_at
    session.add(
        Request(
            house_id=house_id,
            category=RequestCategory.OTHER,
            description="Сделано",
            status=RequestStatus.DONE,
            channel=RequestChannel.MINIAPP,
            created_at=created_at,
            deadline_at=deadline_at,
            accepted_at=(
                None
                if accepted_after is None
                else created_at + timedelta(minutes=accepted_after)
            ),
            reviewed_at=reviewed_at,
            done_at=reviewed_at,
            rating=rating,
        ),
    )
    await session.flush()


async def test_the_house_card_shows_org_stats_from_ten_closed_requests(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user()
    other_house = await _add_house(session, own.org_id)
    foreign = await make_org_house_flat_user()
    now = datetime.now(UTC)
    for index, rating in enumerate((5, 4, 4, None, None, None)):
        await _closed(
            session,
            own.house_id,
            now,
            late=index >= 4,
            accepted_after=10,
            rating=rating,
        )
    for rating in (3, None, None):
        await _closed(session, other_house, now, accepted_after=40, rating=rating)
    session.add(
        Request(
            house_id=own.house_id,
            category=RequestCategory.OTHER,
            description="В работе",
            status=RequestStatus.ACCEPTED,
            channel=RequestChannel.MINIAPP,
            created_at=now - timedelta(days=1),
            deadline_at=now + timedelta(days=1),
            accepted_at=now - timedelta(days=1) + timedelta(minutes=70),
        ),
    )
    await _closed(
        session,
        own.house_id,
        now,
        days_ago=91,
        late=True,
        accepted_after=1000,
        rating=1,
    )
    for _ in range(3):
        await _closed(session, foreign.house_id, now, late=True, rating=1)
    service = _make_service(session)

    nine = await service.house_card(own.house_id, own.user_id, now)
    await _closed(session, other_house, now)
    ten = await service.house_card(own.house_id, own.user_id, now)

    assert nine.org_stats is None
    stats = HouseCard.of(ten, []).org_stats
    assert stats is not None
    assert stats.model_dump() == {
        "closed": 10,
        "on_time": 8,
        "on_time_share": 8000,
        "accept_time": 25,
        "accept_time_median": 10,
        "rating": 400,
        "ratings_count": 4,
    }


async def test_an_unregistered_org_shows_no_stats(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user(registered=False)
    now = datetime.now(UTC)
    for _ in range(10):
        await _closed(session, fixture.house_id, now, rating=5)

    card = await _make_service(session).house_card(
        fixture.house_id,
        fixture.user_id,
        now,
    )

    assert card.org is not None
    assert card.org_stats is None


def test_object_qrs_open_the_request_form_per_entrance_and_object(
    fake_bot: FakeBot,
) -> None:
    house_id = HouseId(7)

    qrs = object_qrs(fake_bot, house_id, 2)

    assert [(qr.category, qr.entrance) for qr in qrs] == [
        (category, entrance) for category in OBJECT_QR_CATEGORIES for entrance in (1, 2)
    ]
    assert qrs[0].deeplink == create_startapp_link(fake_bot, "obj_7_1_elevator")
    assert all("startapp=obj_7_" in qr.deeplink for qr in qrs)


async def test_a_search_finds_a_house_by_any_displayed_form_of_its_address(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    wanted = await _add_house(
        session,
        fixture.org_id,
        city="Москва",
        street="Волгоградский проспект",
        building="105 к.2",
    )
    await _add_house(
        session,
        fixture.org_id,
        city="Москва",
        street="Волгоградский проспект",
        building="105",
    )
    house = await HousesRepo(session).get(wanted)
    assert house is not None
    service = _make_service(session)

    for query in (
        house.address,
        house.street_address,
        "Волгоградский проспект,105 к.2",
        "москва,волгоградский проспект , 105 к.2",
    ):
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


async def test_an_org_search_finds_a_house_by_its_address_with_the_city(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    fixture = await make_org_house_flat_user()
    wanted = await _add_house(
        session,
        fixture.org_id,
        city="Москва",
        street="Ленинский проспект",
        building="61/1",
    )
    await _add_house(
        session,
        fixture.org_id,
        city="Москва",
        street="Ленинский проспект",
        building="62",
    )
    houses = HousesRepo(session)

    for query in ("Москва, Ленинский проспект, 61/1", "ленинский 61", "61/1"):
        found, total = await houses.search_for_org(fixture.org_id, query, 20, 0)
        assert (total, [house.id for house in found]) == (1, [wanted]), query
