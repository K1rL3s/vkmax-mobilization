import json
import secrets
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    add_resident,
    empty_bot_setup,
    make_bot_config,
    make_config,
    make_notifications_service,
    signed_init_data,
)

from zheka.api.app import app_factory
from zheka.api.schemas.announcements import CreateAnnouncementRequest
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.deeplinks import poll_app_path
from zheka.core.enums import (
    AnnouncementChannel,
    ChatStatus,
    EventType,
    NoticeStatus,
    OrgRole,
    PollAuthor,
    ResidentRole,
    ResidentStatus,
)
from zheka.core.errors import (
    FLAT_NOT_FOUND,
    HOUSE_NOT_FOUND,
    NO_BOT_DIALOG,
    EntityNotFound,
    InvalidRequest,
    InvalidState,
)
from zheka.core.ids import FlatId, HouseId, MaxChatId, MaxUserId, UserId
from zheka.core.services.announcements import (
    ANNOUNCEMENT_NOT_FOUND,
    ANNOUNCEMENT_TEXT_LIMIT,
    EMPTY_TEXT,
    ENTRANCES_OR_FLATS,
    FLATS_NOT_IN_CHAT,
    NO_CHANNELS,
    NO_SUCH_ENTRANCE,
    SCOPE_NEEDS_DIRECT,
    SCOPE_OF_ONE_HOUSE,
    TEXT_TOO_LONG,
    AnnouncementData,
    AnnouncementsService,
)
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.texts import VOTE
from zheka.infra.database.models import (
    Chat,
    Flat,
    House,
    OrgMember,
    Organization,
    Resident,
    User,
)
from zheka.infra.database.repos.announcements import AnnouncementsRepo
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.announcements import announcements_table
from zheka.infra.database.tables.events import events_table
from zheka.infra.pdf import NoticeRegisterPdf, PdfDocument

TEXT = "Завтра отключат воду с 9 до 15"


def _service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
) -> AnnouncementsService:
    return AnnouncementsService(
        AnnouncementsRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        ChatsRepo(session),
        OrgsRepo(session),
        make_notifications_service(session, publisher),
        EventsService(EventsRepo(session)),
        FilesService(make_config().files, "test-token"),
        UsersRepo(session),
    )


async def _bind_chat(
    session: AsyncSession,
    house_id: HouseId,
    *,
    status: ChatStatus = ChatStatus.ACTIVE,
    bot_is_admin: bool = True,
) -> MaxChatId:
    chat_id = MaxChatId(secrets.randbits(48))
    session.add(
        Chat(
            chat_id=chat_id,
            house_id=house_id,
            status=status,
            bound_at=datetime.now(UTC),
            bot_is_admin=bot_is_admin,
        ),
    )
    await session.flush()
    return chat_id


async def _add_resident(
    session: AsyncSession,
    house_id: HouseId,
    status: ResidentStatus = ResidentStatus.ACTIVE,
    *,
    flat_id: FlatId | None = None,
    verified: bool = False,
) -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name="Сосед")
    session.add(user)
    await session.flush()
    session.add(
        Resident(
            user_id=user.id,
            house_id=house_id,
            flat_id=flat_id,
            role=ResidentRole.OWNER,
            status=status,
            verified_at=datetime.now(UTC) if verified else None,
        ),
    )
    await session.flush()
    return user.id


async def _org_count(session: AsyncSession, data: OrgHouseFlatUser) -> int:
    stmt = (
        select(func.count())
        .select_from(announcements_table)
        .where(announcements_table.c.org_id == data.org_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def test_house_of_another_org_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    mine = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    foreign = await make_org_house_flat_user()

    with pytest.raises(EntityNotFound):
        await _service(session, publisher).create(
            mine.org_id,
            mine.user_id,
            [mine.house_id, foreign.house_id],
            TEXT,
            [AnnouncementChannel.CHAT],
        )

    await publisher.flush()
    assert await _org_count(session, mine) == 0
    assert broker.messages == []


@pytest.mark.parametrize(
    ("text", "channels", "message"),
    [
        ("   ", [AnnouncementChannel.CHAT], EMPTY_TEXT),
        (
            "я" * (ANNOUNCEMENT_TEXT_LIMIT + 1),
            [AnnouncementChannel.CHAT],
            TEXT_TOO_LONG,
        ),
        (TEXT, [], NO_CHANNELS),
    ],
    ids=["empty", "too_long", "no_channels"],
)
async def test_empty_or_long_text_and_no_channels_are_rejected(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    text: str,
    channels: list[AnnouncementChannel],
    message: str,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)

    with pytest.raises(InvalidRequest, match=message):
        await _create(_service(session), data, text=text, channels=channels)


@pytest.mark.parametrize(
    "chat",
    [
        None,
        {"status": ChatStatus.REMOVED},
        {"bot_is_admin": False},
    ],
    ids=["no-chat", "removed", "not-admin"],
)
async def test_house_without_a_reachable_chat_is_reported_back(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
    chat: dict[str, Any] | None,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    if chat is not None:
        await _bind_chat(session, data.house_id, **chat)

    created = await _create(_service(session, publisher), data)

    await publisher.flush()
    assert list(created.houses_without_chat) == [data.house_id]
    assert created.announcement.recipients_count == 0
    assert created.announcement.delivered_count == 0
    assert broker.enqueued(TaskName.BROADCAST_TO_CHATS) == []


async def test_bound_chat_gets_the_announcement(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _bind_chat(session, data.house_id)

    created = await _create(_service(session, publisher), data)

    await publisher.flush()
    assert list(created.houses_without_chat) == []
    assert created.announcement.recipients_count == 1
    enqueued = broker.enqueued(TaskName.BROADCAST_TO_CHATS)
    assert len(enqueued) == 1
    assert enqueued[0]["chat_ids"] == [chat_id]
    assert enqueued[0]["text"].endswith(f"{TEXT}\n\n#объявление")


async def test_direct_channel_reaches_active_residents_only(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    active = await _add_resident(session, data.house_id)
    await _add_resident(session, data.house_id, ResidentStatus.BLOCKED)

    created = await _create(
        _service(session, publisher),
        data,
        channels=[AnnouncementChannel.DIRECT],
    )

    await publisher.flush()
    enqueued = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert len(enqueued) == 1
    assert enqueued[0]["user_ids"] == [active]
    assert enqueued[0]["text"].endswith(TEXT)
    assert enqueued[0]["category"] == "announcements"
    assert enqueued[0]["mandatory"] is False
    assert created.announcement.recipients_count == 1


async def test_both_channels_record_an_event_each(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    await _bind_chat(session, data.house_id)
    await _add_resident(session, data.house_id)

    created = await _create(
        _service(session, publisher),
        data,
        channels=[AnnouncementChannel.CHAT, AnnouncementChannel.DIRECT],
    )

    assert created.announcement.recipients_count == 2
    stmt = select(events_table.c.payload).where(
        events_table.c.user_id == data.user_id,
        events_table.c.type == EventType.ANNOUNCEMENT_SENT.value,
    )
    result = await session.execute(stmt)
    payloads = result.scalars().all()
    assert {payload["channel"] for payload in payloads} == {"chat", "direct"}
    assert {payload["houses_count"] for payload in payloads} == {1}


async def test_resident_sees_only_announcements_of_own_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    mine = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    other = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    service = _service(session)
    await _create(service, mine)
    await _create(service, other, text="Чужое объявление")

    items, total = await service.list_for_resident(mine.house_id, None, False, 20, 0)

    assert total == 1
    assert items[0].announcement.text == TEXT
    assert items[0].org_name is not None


async def test_org_list_filters_by_house_of_the_same_org(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    mine = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    foreign = await make_org_house_flat_user()
    service = _service(session)
    await _create(service, mine)

    items, total = await service.list_for_org(mine.org_id, mine.house_id, None, 20, 0)
    assert total == 1
    assert items[0].announcement.text == TEXT

    with pytest.raises(EntityNotFound):
        await service.list_for_org(mine.org_id, foreign.house_id, None, 20, 0)


@pytest.mark.parametrize(
    ("urgent", "heading"),
    [(True, "🚨 Срочное объявление"), (False, "📢 Объявление")],
)
async def test_urgent_mark_reaches_the_feed_and_the_message(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
    urgent: bool,
    heading: str,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    await _bind_chat(session, data.house_id)
    service = _service(session, publisher)

    await _create(service, data, urgent=urgent)

    await publisher.flush()
    items, _ = await service.list_for_resident(data.house_id, None, False, 20, 0)
    assert items[0].announcement.urgent is urgent
    assert broker.enqueued(TaskName.BROADCAST_TO_CHATS)[0]["text"].startswith(heading)


async def test_text_of_the_limit_is_accepted(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)

    text = "я" * ANNOUNCEMENT_TEXT_LIMIT
    created = await _create(_service(session), data, text=text)

    assert created.announcement.text == text


async def _create(
    service: AnnouncementsService,
    data: OrgHouseFlatUser,
    *,
    text: str = TEXT,
    channels: Sequence[AnnouncementChannel] = (AnnouncementChannel.CHAT,),
    urgent: bool = False,
) -> AnnouncementData:
    return await service.create(
        data.org_id,
        data.user_id,
        [data.house_id],
        text,
        channels,
        urgent=urgent,
    )


async def test_a_demo_org_sends_a_direct_announcement_only_to_its_author(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    await _add_resident(session, data.house_id)
    org = await OrgsRepo(session).get(data.org_id)
    assert org is not None
    org.is_demo = True
    await session.flush()

    await _create(
        _service(session, publisher),
        data,
        channels=[AnnouncementChannel.DIRECT],
    )

    await publisher.flush()
    [enqueued] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert enqueued["user_ids"] == [data.user_id]


async def test_a_channel_without_addressees_is_reported_at_once(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    await _add_resident(session, data.house_id)

    created = await _create(
        _service(session, publisher),
        data,
        channels=[AnnouncementChannel.CHAT, AnnouncementChannel.DIRECT],
    )

    announcement = created.announcement
    await publisher.flush()
    [enqueued] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert enqueued["announcement_id"] == announcement.id
    assert broker.enqueued(TaskName.BROADCAST_TO_CHATS) == []
    assert announcement.delivered_chat == 0
    assert announcement.delivered_count is None

    await AnnouncementsRepo(session).set_delivered(announcement.id, direct=1)
    await session.refresh(announcement)
    assert announcement.delivered_chat == 0
    assert announcement.delivered_count == 1


async def test_a_direct_only_announcement_waits_for_the_direct_count(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    await _add_resident(session, data.house_id)

    created = await _create(
        _service(session, publisher),
        data,
        channels=[AnnouncementChannel.DIRECT],
    )

    assert created.announcement.delivered_chat == 0
    assert created.announcement.delivered_direct is None


async def _two_entrances(
    session: AsyncSession,
    data: OrgHouseFlatUser,
) -> tuple[FlatId, FlatId]:
    house = await HousesRepo(session).get(data.house_id)
    assert house is not None
    house.entrances = 2
    first = Flat(house_id=data.house_id, number="11", entrance=1)
    second = Flat(house_id=data.house_id, number="21", entrance=2)
    session.add_all([first, second])
    await session.flush()
    return first.id, second.id


async def test_an_entrance_announcement_reaches_and_shows_only_that_entrance(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    first, second = await _two_entrances(session, data)
    await _add_resident(session, data.house_id, flat_id=first)
    neighbour = await _add_resident(session, data.house_id, flat_id=second)
    await _add_resident(session, data.house_id)
    service = _service(session, publisher)

    created = await service.create(
        data.org_id,
        data.user_id,
        [data.house_id],
        TEXT,
        [AnnouncementChannel.DIRECT],
        entrances=[2],
    )

    await publisher.flush()
    [enqueued] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert enqueued["user_ids"] == [neighbour]
    assert "\n📍 Подъезд 2\n" in enqueued["text"]
    assert created.announcement.recipients_count == 1
    _, seen = await service.list_for_resident(data.house_id, second, False, 20, 0)
    _, unseen = await service.list_for_resident(data.house_id, first, False, 20, 0)
    _, no_flat = await service.list_for_resident(data.house_id, None, False, 20, 0)
    assert (seen, unseen, no_flat) == (1, 0, 0)


async def test_a_flat_announcement_reaches_only_verified_residents_of_the_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    first, second = await _two_entrances(session, data)
    verified = await _add_resident(session, data.house_id, flat_id=first, verified=True)
    await _add_resident(session, data.house_id, flat_id=first)
    await _add_resident(session, data.house_id, flat_id=second, verified=True)
    service = _service(session, publisher)

    await service.create(
        data.org_id,
        data.user_id,
        [data.house_id],
        TEXT,
        [AnnouncementChannel.DIRECT],
        flat_ids=[first],
    )

    await publisher.flush()
    [enqueued] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert enqueued["user_ids"] == [verified]
    assert "\n📍 Для вашей квартиры\n" in enqueued["text"]
    _, seen = await service.list_for_resident(data.house_id, first, True, 20, 0)
    _, claimed = await service.list_for_resident(data.house_id, first, False, 20, 0)
    _, other = await service.list_for_resident(data.house_id, second, True, 20, 0)
    assert (seen, claimed, other) == (1, 0, 0)


Scope = Callable[[FlatId, FlatId], tuple[list[int] | None, list[FlatId] | None]]


@pytest.mark.parametrize(
    ("scope", "channels", "error", "message"),
    [
        (
            lambda own, _: ([1], [own]),
            [AnnouncementChannel.DIRECT],
            InvalidRequest,
            ENTRANCES_OR_FLATS,
        ),
        (
            lambda _, __: ([1], None),
            [AnnouncementChannel.CHAT],
            InvalidRequest,
            SCOPE_NEEDS_DIRECT,
        ),
        (
            lambda _, __: ([2], None),
            [AnnouncementChannel.DIRECT],
            InvalidRequest,
            NO_SUCH_ENTRANCE,
        ),
        (
            lambda _, __: ([0], None),
            [AnnouncementChannel.DIRECT],
            InvalidRequest,
            NO_SUCH_ENTRANCE,
        ),
        (
            lambda own, _: (None, [own]),
            [AnnouncementChannel.CHAT, AnnouncementChannel.DIRECT],
            InvalidRequest,
            FLATS_NOT_IN_CHAT,
        ),
        (
            lambda _, foreign: (None, [foreign]),
            [AnnouncementChannel.DIRECT],
            EntityNotFound,
            FLAT_NOT_FOUND,
        ),
    ],
    ids=[
        "both",
        "chat_only",
        "past_entrances",
        "entrance_zero",
        "flats_to_chat",
        "foreign_flat",
    ],
)
async def test_a_wrong_scope_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    scope: Scope,
    channels: list[AnnouncementChannel],
    error: type[Exception],
    message: str,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    foreign = await make_org_house_flat_user()
    entrances, flat_ids = scope(data.flat_id, foreign.flat_id)

    with pytest.raises(error, match=message):
        await _service(session).create(
            data.org_id,
            data.user_id,
            [data.house_id],
            TEXT,
            channels,
            entrances=entrances,
            flat_ids=flat_ids,
        )


async def test_an_entrance_of_two_houses_is_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    second = House(
        org_id=data.org_id,
        region="Тестовая область",
        city="Тестоград",
        street="Тестовая",
        building="2",
        chat_binding_code=secrets.token_hex(4),
        timezone="Europe/Moscow",
    )
    session.add(second)
    await session.flush()

    with pytest.raises(InvalidRequest, match=SCOPE_OF_ONE_HOUSE):
        await _service(session).create(
            data.org_id,
            data.user_id,
            [data.house_id, second.id],
            TEXT,
            [AnnouncementChannel.DIRECT],
            entrances=[1],
        )


@pytest.mark.parametrize("field", ["entrances", "flat_ids"])
def test_an_empty_scope_is_not_the_whole_house(field: str) -> None:
    with pytest.raises(ValidationError):
        CreateAnnouncementRequest.model_validate(
            {"house_ids": [1], "text": TEXT, "channels": ["direct"], field: []},
        )


async def test_the_feed_route_hides_a_flat_announcement_from_a_claimed_resident(
    bot_session: AsyncSession,
) -> None:
    org = Organization(
        name=f"УК {secrets.token_hex(4)}",
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Тестовая область, Тестоград, Тестовая, 1",
        registered_at=datetime.now(UTC),
        timezone="Europe/Moscow",
    )
    bot_session.add(org)
    await bot_session.flush()
    house = House(
        org_id=org.id,
        region="Тестовая область",
        city="Тестоград",
        street="Тестовая",
        building=secrets.token_hex(4),
        chat_binding_code=secrets.token_hex(4),
        timezone="Europe/Moscow",
        entrances=2,
    )
    bot_session.add(house)
    await bot_session.flush()
    flat = Flat(house_id=house.id, number="1", entrance=1)
    bot_session.add(flat)
    await bot_session.flush()
    house_id, flat_id = house.id, flat.id
    headers = {}
    for who in ("staff", "verified", "claimed"):
        user = User(max_user_id=MaxUserId(secrets.randbits(40)), name="Сосед")
        bot_session.add(user)
        await bot_session.flush()
        if who == "staff":
            bot_session.add(
                OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.ADMIN),
            )
        else:
            await add_resident(
                bot_session,
                user.id,
                house_id,
                flat_id,
                verified=who == "verified",
            )
        init_data = signed_init_data(
            datetime.now(UTC),
            user=json.dumps({"id": user.max_user_id, "first_name": "Сосед"}),
        )
        headers[who] = {"WebAppData": init_data}
    await bot_session.commit()
    app = app_factory(make_bot_config(), empty_bot_setup())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        sent = [
            await client.post(
                "/api/admin/announcements",
                headers=headers["staff"],
                json={
                    "house_ids": [house_id],
                    "text": TEXT,
                    "channels": ["direct"],
                    **scope,
                },
            )
            for scope in ({"flat_ids": [flat_id]}, {"entrances": [2]})
        ]
        feeds = {
            who: (await client.get("/api/announcements", headers=headers[who])).json()
            for who in ("verified", "claimed")
        }

    assert [response.status_code for response in sent] == [200, 200]
    assert [item["flats_count"] for item in feeds["verified"]["items"]] == [1]
    assert feeds["claimed"]["items"] == []


async def test_the_register_lists_every_flat_and_whom_the_message_went_to(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    empty = Flat(house_id=data.house_id, number="2")
    session.add(empty)
    await session.flush()
    owner = await _add_resident(
        session,
        data.house_id,
        flat_id=data.flat_id,
        verified=True,
    )
    flatless = await _add_resident(session, data.house_id)
    service = _service(session)
    created = await _create(service, data, channels=[AnnouncementChannel.DIRECT])
    announcement_id = created.announcement.id

    register = await service.register(data.org_id, announcement_id, None)

    [first, second] = register.flats
    assert (first.flat.id, second.flat.id) == (data.flat_id, empty.id)
    assert [
        (row.user_id, row.role, row.verified, row.status) for row in first.deliveries
    ] == [(owner, ResidentRole.OWNER, True, NoticeStatus.PENDING)]
    assert second.deliveries == []
    assert [row.user_id for row in register.without_flat] == [flatless]
    assert register.flats_delivered == 0

    await AnnouncementsRepo(session).set_deliveries(
        announcement_id,
        {owner: (NoticeStatus.DELIVERED, datetime.now(UTC))},
    )
    session.expire_all()
    delivered = await service.register(data.org_id, announcement_id, data.house_id)
    assert delivered.flats_delivered == 1


@pytest.mark.parametrize("author_lives_here", [True, False])
async def test_a_demo_register_holds_only_its_author(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    author_lives_here: bool,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    await _add_resident(session, data.house_id, flat_id=data.flat_id)
    if author_lives_here:
        session.add(
            Resident(
                user_id=data.user_id,
                house_id=data.house_id,
                flat_id=data.flat_id,
                role=ResidentRole.TENANT,
            ),
        )
    org = await OrgsRepo(session).get(data.org_id)
    assert org is not None
    org.is_demo = True
    await session.flush()
    service = _service(session)
    created = await _create(service, data, channels=[AnnouncementChannel.DIRECT])

    register = await service.register(data.org_id, created.announcement.id, None)

    rows = [*register.flats[0].deliveries, *register.without_flat]
    assert [(row.user_id, row.flat_id) for row in rows] == [
        (data.user_id, data.flat_id if author_lives_here else None),
    ]


async def test_a_register_outside_the_org_or_the_announcement_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    mine = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    foreign = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    other = House(
        org_id=mine.org_id,
        region="Тестовая область",
        city="Тестоград",
        street="Тестовая",
        building="2",
        chat_binding_code=secrets.token_hex(4),
        timezone="Europe/Moscow",
    )
    session.add(other)
    await session.flush()
    service = _service(session)
    created = await _create(service, mine, channels=[AnnouncementChannel.DIRECT])
    announcement_id = created.announcement.id

    with pytest.raises(EntityNotFound, match=ANNOUNCEMENT_NOT_FOUND):
        await service.register(foreign.org_id, announcement_id, None)
    with pytest.raises(EntityNotFound, match=HOUSE_NOT_FOUND):
        await service.register(mine.org_id, announcement_id, other.id)


async def test_a_scoped_register_lists_only_the_flats_it_went_to(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    first, second = await _two_entrances(session, data)
    service = _service(session)
    scopes: list[dict[str, Any]] = [{"entrances": [2]}, {"flat_ids": [first]}]
    listed = []
    for scope in scopes:
        created = await service.create(
            data.org_id,
            data.user_id,
            [data.house_id],
            TEXT,
            [AnnouncementChannel.DIRECT],
            **scope,
        )
        register = await service.register(data.org_id, created.announcement.id, None)
        listed.append([item.flat.id for item in register.flats])

    assert listed == [[second], [first]]


async def test_a_poll_notice_goes_to_residents_with_a_vote_button(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    resident = await _add_resident(session, data.house_id)
    now = datetime.now(UTC)
    poll = await PollsRepo(session).create(
        data.house_id,
        data.org_id,
        data.user_id,
        PollAuthor.STAFF.value,
        "Покраска подъездов",
        None,
        is_multiple=False,
        starts_at=now,
        ends_at=now + timedelta(days=7),
        options=["За", "Против"],
    )
    service = _service(session, publisher)

    created = await service.announce_poll(data.org_id, data.user_id, poll)

    await publisher.flush()
    [enqueued] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    assert enqueued["user_ids"] == [resident]
    assert "Покраска подъездов" in enqueued["text"]
    assert (enqueued["app_button"], enqueued["app_path"]) == (
        VOTE,
        poll_app_path(poll.id),
    )
    assert created.announcement.poll_id == poll.id
    assert created.announcement.channels == [AnnouncementChannel.DIRECT.value]
    items, total = await service.list_for_org(data.org_id, None, poll.id, 20, 0)
    assert (total, items[0].announcement.id) == (1, created.announcement.id)


async def test_the_register_route_serves_only_admins_of_the_org(
    bot_session: AsyncSession,
) -> None:
    houses, orgs = [], []
    for _ in range(2):
        org = Organization(
            name=f"УК {secrets.token_hex(4)}",
            inn=secrets.token_hex(6),
            phone="+70000000000",
            address="Тестовая область, Тестоград, Тестовая, 1",
            registered_at=datetime.now(UTC),
            timezone="Europe/Moscow",
        )
        bot_session.add(org)
        await bot_session.flush()
        house = House(
            org_id=org.id,
            region="Тестовая область",
            city="Тестоград",
            street="Тестовая",
            building=secrets.token_hex(4),
            chat_binding_code=secrets.token_hex(4),
            timezone="Europe/Moscow",
        )
        bot_session.add(house)
        await bot_session.flush()
        houses.append(house)
        orgs.append(org.id)
    flat = Flat(house_id=houses[0].id, number="1")
    bot_session.add(flat)
    await bot_session.flush()
    house_id, flat_id = houses[0].id, flat.id
    roles = {
        "admin": (orgs[0], OrgRole.ADMIN),
        "employee": (orgs[0], OrgRole.EMPLOYEE),
        "resident": None,
        "foreign": (orgs[1], OrgRole.ADMIN),
    }
    headers = {}
    for who, role in roles.items():
        max_user_id = MaxUserId(secrets.randbits(40))
        user = User(
            max_user_id=max_user_id,
            max_chat_id=MaxChatId(max_user_id),
            name="Сосед",
        )
        bot_session.add(user)
        await bot_session.flush()
        if role is None:
            await add_resident(bot_session, user.id, house_id, flat_id, verified=True)
        else:
            bot_session.add(OrgMember(org_id=role[0], user_id=user.id, role=role[1]))
        init_data = signed_init_data(
            datetime.now(UTC),
            user=json.dumps({"id": user.max_user_id, "first_name": "Сосед"}),
        )
        headers[who] = {"WebAppData": init_data}
    await bot_session.commit()
    app = app_factory(make_bot_config(), empty_bot_setup())
    poll = {
        "house_id": house_id,
        "title": "Покраска подъездов",
        "options": ["За", "Против"],
        "ends_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        polls = [
            await client.post(
                "/api/admin/polls",
                headers=headers["admin"],
                json={**poll, "notify_residents": notify},
            )
            for notify in (True, False)
        ]
        notices = [
            await client.get(
                "/api/admin/announcements",
                headers=headers["admin"],
                params={"poll_id": created.json()["id"]},
            )
            for created in polls
        ]
        [notice] = notices[0].json()["items"]
        path = f"/api/admin/announcements/{notice['id']}/register"
        answers = {who: await client.get(path, headers=headers[who]) for who in headers}
        pdfs = {
            who: await client.post(f"{path}/pdf", headers=headers[who])
            for who in headers
        }

    assert [notice.json()["total"] for notice in notices] == [1, 0]
    assert {who: answer.status_code for who, answer in answers.items()} == {
        "admin": 200,
        "employee": 403,
        "resident": 403,
        "foreign": 404,
    }
    assert {who: answer.status_code for who, answer in pdfs.items()} == {
        "admin": 200,
        "employee": 403,
        "resident": 403,
        "foreign": 404,
    }
    register = answers["admin"].json()
    assert register["is_demo"] is False
    assert register["announcement"]["poll_id"] == polls[0].json()["id"]
    [row] = register["flats"]
    assert [item["status"] for item in row["recipients"]] == ["pending"]


async def test_a_register_of_one_house_leaves_out_the_other_houses(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    other = House(
        org_id=data.org_id,
        region="Тестовая область",
        city="Тестоград",
        street="Тестовая",
        building="2",
        chat_binding_code=secrets.token_hex(4),
        timezone="Europe/Moscow",
    )
    session.add(other)
    await session.flush()
    here = await _add_resident(session, data.house_id)
    there = await _add_resident(session, other.id)
    both = await _add_resident(session, data.house_id)
    session.add(Resident(user_id=both, house_id=other.id, role=ResidentRole.OWNER))
    await session.flush()
    service = _service(session)
    created = await service.create(
        data.org_id,
        data.user_id,
        [data.house_id, other.id],
        TEXT,
        [AnnouncementChannel.DIRECT],
    )

    registers = [
        await service.register(data.org_id, created.announcement.id, house_id)
        for house_id in (data.house_id, other.id)
    ]

    assert created.announcement.recipients_count == 3
    assert [{row.user_id for row in item.without_flat} for item in registers] == [
        {here, both},
        {there},
    ]


@pytest.mark.parametrize("in_dialog", [True, False])
async def test_a_register_pdf_goes_to_the_admin_only_while_the_bot_can_write(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
    in_dialog: bool,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    if in_dialog:
        user = await UsersRepo(session).get_by_id(data.user_id)
        assert user is not None
        user.max_chat_id = MaxChatId(user.max_user_id)
        await session.flush()
    service = _service(session, publisher)
    created = await _create(service, data, channels=[AnnouncementChannel.DIRECT])
    announcement_id = created.announcement.id

    if in_dialog:
        await service.send_register_pdf(
            data.org_id,
            data.user_id,
            announcement_id,
            None,
            unmarked_only=True,
        )
    else:
        with pytest.raises(InvalidState, match=NO_BOT_DIALOG):
            await service.send_register_pdf(
                data.org_id,
                data.user_id,
                announcement_id,
                None,
                unmarked_only=True,
            )

    await publisher.flush()
    expected = {
        "user_id": data.user_id,
        "org_id": data.org_id,
        "announcement_id": announcement_id,
        "house_id": data.house_id,
        "unmarked_only": True,
    }
    assert broker.enqueued(TaskName.SEND_REGISTER_PDF) == (
        [expected] if in_dialog else []
    )


@pytest.mark.parametrize(
    ("unmarked_only", "later", "pending"),
    [
        (False, timedelta(0), "Отправляется…"),
        (True, timedelta(minutes=11), "Нет данных"),
    ],
)
async def test_the_register_pdf_lists_the_flats_the_screen_shows(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    monkeypatch: pytest.MonkeyPatch,
    unmarked_only: bool,
    later: timedelta,
    pending: str,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    empty = Flat(house_id=data.house_id, number="2", entrance=1)
    waiting = Flat(house_id=data.house_id, number="3")
    session.add_all([empty, waiting])
    await session.flush()
    owner = await _add_resident(
        session,
        data.house_id,
        flat_id=data.flat_id,
        verified=True,
    )
    await _add_resident(session, data.house_id, flat_id=waiting.id)
    service = _service(session)
    created = await _create(service, data, channels=[AnnouncementChannel.DIRECT])
    announcement_id = created.announcement.id
    at = datetime.now(UTC)
    await AnnouncementsRepo(session).set_deliveries(
        announcement_id,
        {owner: (NoticeStatus.DELIVERED, at)},
    )
    session.expire_all()
    register = await service.register(data.org_id, announcement_id, None)
    drawn: list[Sequence[Sequence[str]]] = []
    monkeypatch.setattr(
        PdfDocument,
        "grid",
        lambda _self, _headings, rows, _widths: drawn.append(rows),
    )

    NoticeRegisterPdf(
        replace(register, generated_at=register.generated_at + later),
        demo=False,
        unmarked_only=unmarked_only,
    ).render()

    delivered = (
        "1",
        "-",
        "собственник, подтвержден",
        "Доставлено",
        f"{register.house.local(at):%d.%m.%Y %H:%M}",
    )
    unmarked = [
        ("2", "1", "-", "Нет в сервисе", "-"),
        ("3", "-", "собственник, не подтвержден", pending, "-"),
    ]
    assert drawn == [unmarked if unmarked_only else [delivered, *unmarked]]
