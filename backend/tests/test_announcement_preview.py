from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import Fixture, RecordingBroker
from tests.test_announcements import (
    _add_resident,
    _bind_chat,
    _org_count,
    _service,
    _two_entrances,
)

from zheka.api.schemas.announcements import AnnouncementPreviewResponse
from zheka.broker.publisher import TaskPublisher
from zheka.core.enums import (
    AnnouncementChannel,
    NotificationCategory,
    NotificationLevel,
    OrgRole,
    ResidentStatus,
)
from zheka.core.errors import EntityNotFound, InvalidRequest
from zheka.core.services.announcements import EMPTY_TEXT
from zheka.core.texts import ANNOUNCEMENT_HASHTAG
from zheka.infra.database.repos.notifications import NotificationsRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.events import events_table

BOTH = [AnnouncementChannel.CHAT, AnnouncementChannel.DIRECT]


async def _event_count(session: AsyncSession) -> int:
    stmt = select(func.count()).select_from(events_table)
    result = await session.execute(stmt)
    return result.scalar_one()


async def test_the_preview_counts_addressees_and_who_will_not_get_it(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    await _bind_chat(session, data.house_id)
    await _add_resident(session, data.house_id)
    stopped = await _add_resident(session, data.house_id)
    muted = await _add_resident(session, data.house_id)
    await _add_resident(session, data.house_id, ResidentStatus.BLOCKED)
    user = await UsersRepo(session).get_by_id(stopped)
    assert user is not None
    user.bot_stopped_at = datetime.now(UTC)
    await NotificationsRepo(session).set_level(
        muted,
        NotificationCategory.ANNOUNCEMENTS,
        NotificationLevel.OFF,
    )
    await session.flush()
    events_before = await _event_count(session)

    preview = await _service(session, publisher).preview(
        data.org_id,
        data.user_id,
        [data.house_id],
        "Вода <b>& свет</b>",
        BOTH,
        urgent=True,
    )

    await publisher.flush()
    assert preview.message.endswith("\n\nВода <b>& свет</b>")
    assert preview.message.startswith("🚨 Срочное объявление от УК ")
    assert preview.chat_hashtag == ANNOUNCEMENT_HASHTAG
    assert (preview.chats_count, preview.residents_count) == (1, 3)
    assert (preview.bot_stopped_count, preview.muted_count) == (1, 1)
    assert preview.houses_without_chat == []
    assert preview.is_demo is False
    assert AnnouncementPreviewResponse.of(preview).recipients_count == 4
    assert await _org_count(session, data) == 0
    assert await _event_count(session) == events_before
    assert broker.messages == []


async def test_a_demo_preview_counts_the_same_addressees_the_announcement_gets(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    await _bind_chat(session, data.house_id)
    await _add_resident(session, data.house_id)
    await _add_resident(session, data.house_id)
    org = await OrgsRepo(session).get(data.org_id)
    assert org is not None
    org.is_demo = True
    await session.flush()
    service = _service(session, publisher)

    preview = await service.preview(
        data.org_id,
        data.user_id,
        [data.house_id],
        "Уборка двора",
        BOTH,
    )
    created = await service.create(
        data.org_id,
        data.user_id,
        [data.house_id],
        "Уборка двора",
        BOTH,
    )

    assert preview.is_demo is True
    assert preview.residents_count == 1
    assert (
        AnnouncementPreviewResponse.of(preview).recipients_count
        == created.announcement.recipients_count
    )


async def test_an_entrance_preview_names_the_entrance_and_goes_to_no_chat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    _first, second = await _two_entrances(session, data)
    await _add_resident(session, data.house_id, flat_id=second)
    await _add_resident(session, data.house_id)

    preview = await _service(session, publisher).preview(
        data.org_id,
        data.user_id,
        [data.house_id],
        "Промывка стояков",
        [AnnouncementChannel.DIRECT],
        entrances=[2],
    )

    assert "\n📍 Подъезд 2\n" in preview.message
    assert preview.chat_hashtag is None
    assert (preview.chats_count, preview.residents_count) == (0, 1)


async def test_the_preview_refuses_what_sending_refuses(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    publisher: TaskPublisher,
) -> None:
    mine = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    foreign = await make_org_house_flat_user()
    service = _service(session, publisher)

    with pytest.raises(EntityNotFound):
        await service.preview(
            mine.org_id,
            mine.user_id,
            [foreign.house_id],
            "Уборка двора",
            BOTH,
        )
    with pytest.raises(InvalidRequest, match=EMPTY_TEXT):
        await service.preview(
            mine.org_id,
            mine.user_id,
            [mine.house_id],
            "  ",
            BOTH,
        )
