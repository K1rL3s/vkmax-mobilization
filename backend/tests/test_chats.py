import secrets
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser, RecordingBroker, make_notifications_service

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import (
    ChatStatus,
    EventType,
    OrgRole,
    ResidentRole,
    ResidentStatus,
)
from zheka.core.errors import InvalidRequest, InvalidState, NotEnoughRights
from zheka.core.ids import MaxChatId
from zheka.core.services.chats import ChatsService
from zheka.core.services.events import EventsService
from zheka.infra.database.models import Chat
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.tables.events import events_table

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


def _service(
    session: AsyncSession, publisher: TaskPublisher | None = None
) -> ChatsService:
    return ChatsService(
        ChatsRepo(session),
        HousesRepo(session),
        OrgsRepo(session),
        ResidentsRepo(session),
        make_notifications_service(session, publisher),
        EventsService(EventsRepo(session)),
    )


async def _added(session: AsyncSession) -> MaxChatId:
    chat_id = MaxChatId(secrets.randbits(48))
    await _service(session).on_bot_added(chat_id, "Дом")
    return chat_id


async def _chat(session: AsyncSession, chat_id: MaxChatId) -> Chat:
    session.expire_all()
    chat = await ChatsRepo(session).get(chat_id)
    assert chat is not None
    return chat


@pytest.mark.parametrize(
    ("org_role", "by_role"), [(OrgRole.EMPLOYEE, "staff"), (None, "chairman")]
)
async def test_staff_or_the_chairman_binds_the_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    org_role: OrgRole | None,
    by_role: str,
) -> None:
    data = await make_org_house_flat_user(
        org_role=org_role, resident_role=None if org_role else ResidentRole.OWNER
    )
    if org_role is None:
        (await ResidentsRepo(session).list_for_user(data.user_id))[0].is_chairman = True
    chat_id = await _added(session)

    await _service(session).bind(data.user_id, chat_id, data.house_id)

    chat = await _chat(session, chat_id)
    assert chat.house_id == data.house_id
    assert chat.bound_by == data.user_id
    stmt = select(events_table.c.payload).where(
        events_table.c.type == EventType.CHAT_BOUND,
        events_table.c.user_id == data.user_id,
    )
    assert (await session.execute(stmt)).scalar_one()["by_role"] == by_role


async def test_staff_of_another_org_cannot_bind(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    stranger = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    other = await make_org_house_flat_user()
    chat_id = await _added(session)

    with pytest.raises(NotEnoughRights):
        await _service(session).bind(stranger.user_id, chat_id, other.house_id)

    assert (await _chat(session, chat_id)).bound_at is None


@pytest.mark.parametrize(
    ("org_role", "chairman_status"),
    [(OrgRole.EXECUTOR, None), (None, None), (None, ResidentStatus.BLOCKED)],
    ids=["executor", "plain_resident", "blocked_chairman"],
)
async def test_only_staff_or_an_active_chairman_binds(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    org_role: OrgRole | None,
    chairman_status: ResidentStatus | None,
) -> None:
    data = await make_org_house_flat_user(
        org_role=org_role, resident_role=None if org_role else ResidentRole.OWNER
    )
    if chairman_status is not None:
        resident = (await ResidentsRepo(session).list_for_user(data.user_id))[0]
        resident.is_chairman = True
        resident.status = chairman_status
    chat_id = await _added(session)

    with pytest.raises(NotEnoughRights):
        await _service(session).bind(data.user_id, chat_id, data.house_id)

    assert (await _chat(session, chat_id)).bound_at is None


async def test_a_bound_chat_is_not_bound_again(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    first = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    second = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _added(session)
    await _service(session).bind(first.user_id, chat_id, first.house_id)

    with pytest.raises(NotEnoughRights):
        await _service(session).bind(second.user_id, chat_id, second.house_id)

    assert (await _chat(session, chat_id)).house_id == first.house_id


async def test_a_chat_the_bot_left_is_not_bound(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _added(session)
    await _service(session).on_bot_removed(chat_id)

    with pytest.raises(NotEnoughRights):
        await _service(session).bind(data.user_id, chat_id, data.house_id)


async def test_a_wrong_code_binds_nothing(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    data = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    chat_id = await _added(session)

    with pytest.raises(InvalidRequest):
        await _service(session).bind_by_code(data.user_id, chat_id, "00000000")

    assert (await _chat(session, chat_id)).bound_at is None


async def test_the_code_binds_its_house(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    data = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    house = await HousesRepo(session).get(data.house_id)
    assert house is not None
    chat_id = await _added(session)

    await _service(session).bind_by_code(
        data.user_id, chat_id, f" {house.chat_binding_code.upper()} "
    )

    assert (await _chat(session, chat_id)).house_id == data.house_id


async def test_the_rights_are_granted_once_over_two_grants(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _added(session)
    service = _service(session, publisher)
    await service.bind(data.user_id, chat_id, data.house_id)

    await service.set_admin(chat_id, True)
    await service.set_admin(chat_id, True)

    stmt = select(func.count()).where(
        events_table.c.type == EventType.CHAT_ADMIN_GRANTED,
        events_table.c.user_id == data.user_id,
    )
    assert (await session.execute(stmt)).scalar_one() == 1
    assert (await _chat(session, chat_id)).bot_is_admin is True
    await publisher.flush()
    assert broker.enqueued(TaskName.WELCOME_CHAT) == [
        {"chat_id": chat_id, "house_id": data.house_id}
    ]


async def test_the_rights_of_a_chat_the_bot_left_are_not_recorded(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _added(session)
    service = _service(session)
    await service.bind(data.user_id, chat_id, data.house_id)
    await service.on_bot_removed(chat_id)

    with pytest.raises(InvalidState):
        await service.set_admin(chat_id, True)


# событие удаления бота могло не дойти, поэтому сброс не полагается на него
@pytest.mark.parametrize("removed", [True, False])
async def test_a_re_add_clears_the_previous_binding(
    session: AsyncSession, make_org_house_flat_user: Fixture, removed: bool
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _added(session)
    service = _service(session)
    await service.bind(data.user_id, chat_id, data.house_id)
    await service.set_admin(chat_id, True)
    if removed:
        await service.on_bot_removed(chat_id)

    await service.on_bot_added(chat_id, "Дом, новое название")

    chat = await _chat(session, chat_id)
    assert chat.status == ChatStatus.ACTIVE
    assert chat.title == "Дом, новое название"
    assert chat.house_id is None
    assert chat.bound_by is None
    assert chat.bound_at is None
    assert chat.bot_is_admin is False
