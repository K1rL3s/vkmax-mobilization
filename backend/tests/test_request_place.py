from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    add_meter,
    add_reading,
    add_resident,
    admin_requests_service,
    requests_service,
)
from tests.test_charges import _charge, _make_service as charges_service
from tests.test_contact import _viewer
from tests.test_requests import DESCRIPTION, _mark_done, _member, _neighbour

from zheka.api.routes.admin.requests import list_org_requests
from zheka.api.routes.requests import list_request_categories
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import (
    CATEGORY_PLACES,
    OrgRole,
    RequestCategory,
    RequestPlace,
)
from zheka.core.errors import InvalidRequest
from zheka.core.ids import RequestGroupId
from zheka.core.services.admin_requests import PhoneRequestDraft
from zheka.core.services.request_groups import PRIVATE_CATEGORIES
from zheka.core.services.requests import PLACE_REQUIRED, RequestDraft
from zheka.core.texts import REQUEST_PLACE_LINES
from zheka.infra.database.repos.requests import RequestFilters, RequestsRepo

EITHER_PLACE = [
    category for category in RequestCategory if category not in CATEGORY_PLACES
]


def _other(place: RequestPlace) -> RequestPlace:
    return next(item for item in RequestPlace if item is not place)


async def _group_first_in_the_house(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> RequestGroupId:
    service = requests_service(session)
    places = (RequestPlace.HOUSE, RequestPlace.FLAT, RequestPlace.FLAT)
    cards = [
        await service.create(
            await _neighbour(session, own.house_id, f"1{index}"),
            own.house_id,
            RequestDraft(
                category=RequestCategory.LEAK,
                description="Течет стояк",
                place=place,
            ),
        )
        for index, place in enumerate(places)
    ]
    group_id = cards[-1].request.group_id
    assert group_id is not None
    return group_id


def test_lift_chute_entrance_and_yard_are_common_and_bills_are_personal() -> None:
    assert CATEGORY_PLACES == {
        RequestCategory.ELEVATOR: RequestPlace.HOUSE,
        RequestCategory.GARBAGE: RequestPlace.HOUSE,
        RequestCategory.ENTRANCE: RequestPlace.HOUSE,
        RequestCategory.YARD: RequestPlace.HOUSE,
        RequestCategory.METER_ERROR: RequestPlace.FLAT,
        RequestCategory.CHARGE_DISPUTE: RequestPlace.FLAT,
    }
    assert {
        category
        for category, place in CATEGORY_PLACES.items()
        if place is RequestPlace.FLAT
    } == PRIVATE_CATEGORIES


@pytest.mark.parametrize("place", list(RequestPlace))
async def test_a_request_keeps_the_place_the_resident_chose(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    place: RequestPlace,
) -> None:
    card = await requests_service(session).create(
        own.user_id,
        own.house_id,
        RequestDraft(
            category=RequestCategory.LEAK,
            description=DESCRIPTION,
            place=place,
        ),
    )

    assert card.request.place is place
    stored = await RequestsRepo(session).get(card.request.id)
    assert stored is not None
    assert stored.place is place


@pytest.mark.parametrize("category", EITHER_PLACE)
async def test_a_request_of_a_category_with_either_place_needs_the_place(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    category: RequestCategory,
) -> None:
    with pytest.raises(InvalidRequest, match=PLACE_REQUIRED):
        await requests_service(session).create(
            own.user_id,
            own.house_id,
            RequestDraft(category=category, description=DESCRIPTION),
        )


@pytest.mark.parametrize(("category", "place"), list(CATEGORY_PLACES.items()))
async def test_a_category_with_one_place_takes_it_over_the_choice(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    category: RequestCategory,
    place: RequestPlace,
) -> None:
    card = await requests_service(session).create(
        own.user_id,
        own.house_id,
        RequestDraft(category=category, description=DESCRIPTION, place=_other(place)),
    )

    assert card.request.place is place


async def test_joining_a_group_takes_the_place_of_its_first_request(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    group_id = await _group_first_in_the_house(session, own)

    joined = await requests_service(session).create(
        own.user_id,
        own.house_id,
        RequestDraft(
            category=RequestCategory.LEAK,
            description="И у нас",
            group_id=group_id,
        ),
    )

    assert joined.request.group_id == group_id
    assert joined.request.place is RequestPlace.HOUSE


async def test_a_repeat_request_keeps_the_place_of_its_parent(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    parent = await service.create(
        own.user_id,
        own.house_id,
        RequestDraft(
            category=RequestCategory.HEATING,
            description="Холодный стояк в подъезде",
            place=RequestPlace.HOUSE,
        ),
    )
    await _mark_done(session, parent.request.id)

    repeated = await service.repeat(own.user_id, parent.request.id, None, [])

    assert repeated.request.place is RequestPlace.HOUSE


async def test_a_charge_dispute_is_about_the_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    meter_id = await add_meter(session, own.flat_id)
    await add_reading(session, meter_id, date(2026, 3, 1), 1_000, own.user_id)
    charge = await _charge(session, own)

    request_id = await charges_service(session).dispute(
        charge.id,
        own.user_id,
        "Почему так много?",
        None,
    )

    request = await RequestsRepo(session).get(request_id)
    assert request is not None
    assert request.place is RequestPlace.FLAT


@pytest.mark.parametrize("place", list(RequestPlace))
async def test_a_phone_request_keeps_the_place_staff_chose(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    place: RequestPlace,
) -> None:
    card = await admin_requests_service(session).create_phone(
        own.org_id,
        PhoneRequestDraft(
            house_id=own.house_id,
            category=RequestCategory.ELECTRICITY,
            description="Не горит свет",
            flat_id=own.flat_id,
            place=place,
        ),
        own.user_id,
    )

    assert card.card.request.place is place


async def test_a_phone_request_of_a_category_with_either_place_needs_the_place(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    with pytest.raises(InvalidRequest, match=PLACE_REQUIRED):
        await admin_requests_service(session).create_phone(
            own.org_id,
            PhoneRequestDraft(
                house_id=own.house_id,
                category=RequestCategory.ELECTRICITY,
                description="Не горит свет",
                flat_id=own.flat_id,
            ),
            own.user_id,
        )


async def test_a_phone_request_of_a_lift_is_common_without_asking(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    card = await admin_requests_service(session).create_phone(
        own.org_id,
        PhoneRequestDraft(
            house_id=own.house_id,
            category=RequestCategory.ELEVATOR,
            description="Застрял лифт",
            flat_id=own.flat_id,
        ),
        own.user_id,
    )

    assert card.card.request.place is RequestPlace.HOUSE


async def test_the_cabinet_filters_requests_by_place(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = requests_service(session)
    created = {
        place: await service.create(
            own.user_id,
            own.house_id,
            RequestDraft(
                category=RequestCategory.OTHER,
                description=DESCRIPTION,
                place=place,
            ),
        )
        for place in RequestPlace
    }
    viewer = _viewer(own, own.user_id, is_demo=False)

    for place, card in created.items():
        rows, total = await admin_requests_service(session).inbox(
            own.org_id,
            RequestFilters(place=place),
            20,
            0,
        )
        page = await list_org_requests(
            viewer,
            admin_requests_service(session),
            place=place,
        )

        assert total == 1
        assert [row.request.id for row in rows] == [card.request.id]
        assert [(item.id, item.place) for item in page.items] == [
            (card.request.id, place),
        ]


async def test_a_group_is_filtered_by_the_place_of_its_first_request(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    group_id = await _group_first_in_the_house(session, own)
    inbox = admin_requests_service(session)

    common, _ = await inbox.inbox(
        own.org_id,
        RequestFilters(place=RequestPlace.HOUSE, grouped=True),
        20,
        0,
    )
    personal, _ = await inbox.inbox(
        own.org_id,
        RequestFilters(place=RequestPlace.FLAT, grouped=True),
        20,
        0,
    )

    assert [row.request.group_id for row in common] == [group_id]
    assert personal == []


async def test_request_categories_say_which_place_is_fixed(
    own: OrgHouseFlatUser,
) -> None:
    items = await list_request_categories(own)  # type: ignore[arg-type]

    assert {item.category: item.place for item in items} == {
        category: CATEGORY_PLACES.get(category) for category in RequestCategory
    }


async def test_staff_hear_where_the_new_request_is(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    await _member(session, own.org_id, OrgRole.ADMIN)
    await requests_service(session, publisher).create(
        own.user_id,
        own.house_id,
        RequestDraft(
            category=RequestCategory.WATER_SUPPLY,
            description="Нет воды в подъезде",
            place=RequestPlace.HOUSE,
        ),
    )
    await publisher.flush()

    texts = [
        message["text"] for message in broker.enqueued(TaskName.BROADCAST_TO_USERS)
    ]
    assert texts
    assert all(REQUEST_PLACE_LINES[RequestPlace.HOUSE] in text for text in texts)
