import secrets
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    make_notifications_service,
)

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import (
    AnnouncementChannel,
    ChatStatus,
    EventType,
    OrgRole,
    ResidentRole,
    ResidentStatus,
)
from zheka.core.errors import EntityNotFound, InvalidRequest
from zheka.core.ids import HouseId, MaxChatId, MaxUserId, UserId
from zheka.core.services.announcements import (
    ANNOUNCEMENT_TEXT_LIMIT,
    EMPTY_TEXT,
    NO_CHANNELS,
    TEXT_TOO_LONG,
    AnnouncementData,
    AnnouncementsService,
)
from zheka.core.services.events import EventsService
from zheka.infra.database.models import Chat, Resident, User
from zheka.infra.database.repos.announcements import AnnouncementsRepo
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.tables.announcements import announcements_table
from zheka.infra.database.tables.events import events_table

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
) -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name="Сосед")
    session.add(user)
    await session.flush()
    session.add(
        Resident(
            user_id=user.id,
            house_id=house_id,
            role=ResidentRole.OWNER,
            status=status,
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
    assert TEXT in enqueued[0]["text"]


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

    items, total = await service.list_for_resident(mine.house_id, 20, 0)

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

    items, total = await service.list_for_org(mine.org_id, mine.house_id, 20, 0)
    assert total == 1
    assert items[0].announcement.text == TEXT

    with pytest.raises(EntityNotFound):
        await service.list_for_org(mine.org_id, foreign.house_id, 20, 0)


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
    items, _ = await service.list_for_resident(data.house_id, 20, 0)
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
