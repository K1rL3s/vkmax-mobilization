import re
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
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
from zheka.core.services.chats import (
    MESSAGE_TEXT_LIMIT,
    PINS_ERASED,
    PINS_FULL,
    PIN_DENIED,
    PIN_HINT,
    PIN_NEEDS_RIGHTS,
    PIN_TEXT_LIMIT,
    PIN_THE_LIST,
    UNPIN_HINT,
    UNPIN_THE_LIST,
    ChatsService,
    MessageRef,
    pins_text,
)
from zheka.core.services.events import EventsService
from zheka.infra.database.models import Chat, ChatPin
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.tables.chats import chat_pins_table
from zheka.infra.database.tables.events import events_table

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


def _service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
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
    ("org_role", "by_role"),
    [(OrgRole.EMPLOYEE, "staff"), (None, "chairman")],
)
async def test_staff_or_the_chairman_binds_the_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    org_role: OrgRole | None,
    by_role: str,
) -> None:
    data = await make_org_house_flat_user(
        org_role=org_role,
        resident_role=None if org_role else ResidentRole.OWNER,
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
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
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
        org_role=org_role,
        resident_role=None if org_role else ResidentRole.OWNER,
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
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    first = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    second = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _added(session)
    await _service(session).bind(first.user_id, chat_id, first.house_id)

    with pytest.raises(NotEnoughRights):
        await _service(session).bind(second.user_id, chat_id, second.house_id)

    assert (await _chat(session, chat_id)).house_id == first.house_id


async def test_a_chat_the_bot_left_is_not_bound(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _added(session)
    await _service(session).on_bot_removed(chat_id)

    with pytest.raises(NotEnoughRights):
        await _service(session).bind(data.user_id, chat_id, data.house_id)


async def test_a_wrong_code_binds_nothing(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    chat_id = await _added(session)

    with pytest.raises(InvalidRequest):
        await _service(session).bind_by_code(data.user_id, chat_id, "00000000")

    assert (await _chat(session, chat_id)).bound_at is None


async def test_the_code_binds_its_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    house = await HousesRepo(session).get(data.house_id)
    assert house is not None
    chat_id = await _added(session)

    await _service(session).bind_by_code(
        data.user_id,
        chat_id,
        f" {house.chat_binding_code.upper()} ",
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
        {"chat_id": chat_id, "house_id": data.house_id},
    ]


async def test_the_rights_of_a_chat_the_bot_left_are_not_recorded(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _added(session)
    service = _service(session)
    await service.bind(data.user_id, chat_id, data.house_id)
    await service.on_bot_removed(chat_id)

    with pytest.raises(InvalidState):
        await service.set_admin(chat_id, True)


@pytest.mark.parametrize("removed", [True, False])
async def test_a_re_add_clears_the_previous_binding(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    removed: bool,
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


async def test_a_message_is_listed_once_until_it_is_unpinned(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user()
    chat_id = await _added(session)
    first = ChatPin(chat_id=chat_id, mid="m-1", seq=1, pinned_by=data.user_id)
    session.add(first)
    await session.flush()

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                ChatPin(chat_id=chat_id, mid="m-1", seq=1, pinned_by=data.user_id),
            )

    first.unpinned_at = datetime.now(UTC)
    session.add(ChatPin(chat_id=chat_id, mid="m-1", seq=1, pinned_by=data.user_id))
    await session.flush()


REPLY = MessageRef(mid="m-1", seq=1)


async def _pinning_chat(session: AsyncSession, data: OrgHouseFlatUser) -> MaxChatId:
    chat_id = await _added(session)
    chat = await _chat(session, chat_id)
    await ChatsRepo(session).bind(chat, data.house_id, data.user_id)
    await ChatsRepo(session).set_admin(chat, True)
    return chat_id


async def _listed(
    session: AsyncSession,
    chat_id: MaxChatId,
) -> list[tuple[str, str | None]]:
    session.expire_all()
    return [(pin.mid, pin.text) for pin in await ChatsRepo(session).list_pins(chat_id)]


async def _pin_events(
    session: AsyncSession,
    chat_id: MaxChatId,
    event: EventType,
) -> list[dict[str, Any]]:
    stmt = (
        select(events_table.c.payload)
        .where(
            events_table.c.type == event,
            events_table.c.payload["chat_id"].astext == str(chat_id),
        )
        .order_by(events_table.c.id)
    )
    return list((await session.execute(stmt)).scalars())


@pytest.mark.parametrize(
    ("org_role", "by_role"),
    [(OrgRole.EMPLOYEE, "staff"), (None, "chairman")],
)
async def test_staff_or_the_chairman_pins_a_message(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
    org_role: OrgRole | None,
    by_role: str,
) -> None:
    data = await make_org_house_flat_user(
        org_role=org_role,
        resident_role=None if org_role else ResidentRole.OWNER,
    )
    if org_role is None:
        (await ResidentsRepo(session).list_for_user(data.user_id))[0].is_chairman = True
    chat_id = await _pinning_chat(session, data)

    await _service(session, publisher).pin(
        data.user_id,
        chat_id,
        REPLY,
        "  Отключение воды  ",
    )

    assert await _listed(session, chat_id) == [("m-1", "Отключение воды")]
    assert await _pin_events(session, chat_id, EventType.CHAT_PINNED) == [
        {"chat_id": chat_id, "house_id": data.house_id, "by_role": by_role},
    ]
    await publisher.flush()
    assert broker.enqueued(TaskName.SYNC_CHAT_PINS) == [
        {"chat_id": chat_id, "notify": True, "resend": False},
    ]


@pytest.mark.parametrize(
    ("org_role", "resident_role"),
    [(OrgRole.EXECUTOR, None), (None, ResidentRole.OWNER)],
)
async def test_an_executor_or_a_resident_cannot_pin(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    org_role: OrgRole | None,
    resident_role: ResidentRole | None,
) -> None:
    data = await make_org_house_flat_user(
        org_role=org_role,
        resident_role=resident_role,
    )
    chat_id = await _pinning_chat(session, data)

    with pytest.raises(NotEnoughRights, match=re.escape(PIN_DENIED)):
        await _service(session).pin(data.user_id, chat_id, REPLY, None)
    with pytest.raises(NotEnoughRights, match=re.escape(PIN_DENIED)):
        await _service(session).repin(data.user_id, chat_id)

    assert await _listed(session, chat_id) == []


async def test_a_chat_without_a_house_ignores_pins(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _added(session)
    service = _service(session, publisher)

    await service.pin(data.user_id, chat_id, REPLY, None)
    await service.unpin(data.user_id, chat_id, None, None)

    assert await _listed(session, chat_id) == []
    await publisher.flush()
    assert broker.enqueued(TaskName.SYNC_CHAT_PINS) == []


async def test_a_pin_needs_a_reply_and_the_bot_rights(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _pinning_chat(session, data)
    service = _service(session)

    with pytest.raises(InvalidRequest, match=re.escape(PIN_HINT)):
        await service.pin(data.user_id, chat_id, None, "Вода")
    await ChatsRepo(session).set_admin(await _chat(session, chat_id), False)
    with pytest.raises(InvalidState, match=re.escape(PIN_NEEDS_RIGHTS)):
        await service.pin(data.user_id, chat_id, REPLY, None)

    assert await _listed(session, chat_id) == []


async def test_a_repeat_pin_replaces_the_text_of_its_item(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _pinning_chat(session, data)
    service = _service(session)

    await service.pin(data.user_id, chat_id, REPLY, "в" * (PIN_TEXT_LIMIT + 5))
    assert await _listed(session, chat_id) == [("m-1", "в" * PIN_TEXT_LIMIT)]
    await service.pin(data.user_id, chat_id, REPLY, None)

    assert await _listed(session, chat_id) == [("m-1", None)]
    assert len(await _pin_events(session, chat_id, EventType.CHAT_PINNED)) == 1


async def test_the_list_takes_a_pin_while_it_fits_one_max_message(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _pinning_chat(session, data)
    service = _service(session)
    repo = ChatsRepo(session)
    first = ChatPin(chat_id=chat_id, mid="m-1", seq=1, text="в", pinned_by=data.user_id)
    await repo.add_pin(first)
    # 😀 is one code point but two UTF-16 units, the way MAX counts
    second = ChatPin(
        chat_id=chat_id,
        mid="m-2",
        seq=2,
        text="😀",
        pinned_by=data.user_id,
    )
    room = MESSAGE_TEXT_LIMIT - _utf16_units(pins_text(chat_id, [first, second]))
    second_ref = MessageRef(mid="m-2", seq=2)

    await repo.set_pin_text(first, "в" * (room + 2))
    with pytest.raises(InvalidRequest, match=re.escape(PINS_FULL)):
        await service.pin(data.user_id, chat_id, second_ref, "😀")
    await repo.set_pin_text(first, "в" * (room + 1))
    await service.pin(data.user_id, chat_id, second_ref, "😀")
    with pytest.raises(InvalidRequest, match=re.escape(PINS_FULL)):
        await service.pin(data.user_id, chat_id, second_ref, "😀в")
    assert await _listed(session, chat_id) == [
        ("m-1", "в" * (room + 1)),
        ("m-2", "😀"),
    ]
    await service.pin(data.user_id, chat_id, second_ref, "вв")

    pins = await repo.list_pins(chat_id)
    assert [pin.text for pin in pins] == ["в" * (room + 1), "вв"]
    assert _utf16_units(pins_text(chat_id, pins)) == MESSAGE_TEXT_LIMIT


async def test_unpin_by_number_or_by_reply_and_the_numbers_close_up(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _pinning_chat(session, data)
    service = _service(session)
    for seq in (1, 2, 3):
        await service.pin(
            data.user_id,
            chat_id,
            MessageRef(mid=f"m-{seq}", seq=seq),
            None,
        )

    await service.unpin(data.user_id, chat_id, None, 1)
    await service.unpin(data.user_id, chat_id, None, 2)
    assert await _listed(session, chat_id) == [("m-2", None)]
    await service.unpin(data.user_id, chat_id, MessageRef(mid="m-2", seq=2), None)

    assert await _listed(session, chat_id) == []
    events = await _pin_events(session, chat_id, EventType.CHAT_UNPINNED)
    assert [event["method"] for event in events] == ["number", "number", "reply"]
    assert {event["by_role"] for event in events} == {"staff"}
    stmt = select(func.count()).where(
        chat_pins_table.c.chat_id == chat_id,
        chat_pins_table.c.unpinned_at.is_not(None),
    )
    assert (await session.execute(stmt)).scalar_one() == 3


@pytest.mark.parametrize(
    ("target", "number"),
    [(None, None), (None, 0), (None, 4), (MessageRef(mid="m-9", seq=9), None)],
)
async def test_an_unpin_that_names_no_item_is_a_hint(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    target: MessageRef | None,
    number: int | None,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _pinning_chat(session, data)
    service = _service(session)
    for seq in (1, 2, 3):
        await service.pin(
            data.user_id,
            chat_id,
            MessageRef(mid=f"m-{seq}", seq=seq),
            None,
        )

    with pytest.raises(InvalidRequest, match=re.escape(UNPIN_HINT)):
        await service.unpin(data.user_id, chat_id, target, number)

    assert len(await _listed(session, chat_id)) == 3


async def test_a_deleted_pin_leaves_the_list_and_a_deleted_list_is_erased(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _pinning_chat(session, data)
    service = _service(session, publisher)
    for seq in (1, 2, 3):
        await service.pin(
            data.user_id,
            chat_id,
            MessageRef(mid=f"m-{seq}", seq=seq),
            None,
        )
    await ChatsRepo(session).set_pins_mid(await _chat(session, chat_id), "list-1")
    await publisher.flush()
    broker.messages.clear()

    await service.on_message_removed(chat_id, "m-9")
    assert len(await _listed(session, chat_id)) == 3
    await service.on_message_removed(chat_id, "m-1")
    assert [mid for mid, _ in await _listed(session, chat_id)] == ["m-2", "m-3"]
    await publisher.flush()
    assert broker.enqueued(TaskName.SYNC_CHAT_PINS) == [
        {"chat_id": chat_id, "notify": False, "resend": False},
    ]
    await service.on_message_removed(chat_id, "list-1")

    assert await _listed(session, chat_id) == []
    assert (await _chat(session, chat_id)).pins_mid is None
    events = await _pin_events(session, chat_id, EventType.CHAT_UNPINNED)
    assert [event["method"] for event in events] == [
        "message_deleted",
        "list_deleted",
        "list_deleted",
    ]
    await publisher.flush()
    assert broker.enqueued(TaskName.BROADCAST_TO_CHATS) == [
        {"chat_ids": [chat_id], "text": PINS_ERASED},
    ]


async def test_a_re_add_drops_the_old_list_without_events(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _pinning_chat(session, data)
    service = _service(session)
    await service.pin(data.user_id, chat_id, REPLY, None)
    await ChatsRepo(session).set_pins_mid(await _chat(session, chat_id), "list-1")

    await service.on_bot_added(chat_id, "Дом")

    assert await _listed(session, chat_id) == []
    assert (await _chat(session, chat_id)).pins_mid is None
    assert await _pin_events(session, chat_id, EventType.CHAT_UNPINNED) == []


async def test_the_list_itself_is_neither_pinned_nor_unpinned(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _pinning_chat(session, data)
    service = _service(session)
    await service.pin(data.user_id, chat_id, REPLY, None)
    await ChatsRepo(session).set_pins_mid(await _chat(session, chat_id), "list-1")
    the_list = MessageRef(mid="list-1", seq=50)

    with pytest.raises(InvalidRequest, match=re.escape(PIN_THE_LIST)):
        await service.pin(data.user_id, chat_id, the_list, None)
    with pytest.raises(InvalidRequest, match=re.escape(UNPIN_THE_LIST)):
        await service.unpin(data.user_id, chat_id, the_list, None)

    assert await _listed(session, chat_id) == [("m-1", None)]


def _utf16_units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


async def test_repin_resends_a_list_that_has_items(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _pinning_chat(session, data)
    service = _service(session, publisher)

    with pytest.raises(InvalidRequest, match=re.escape(PIN_HINT)):
        await service.repin(data.user_id, chat_id)
    await service.pin(data.user_id, chat_id, REPLY, None)
    await service.repin(data.user_id, chat_id)

    await publisher.flush()
    assert broker.enqueued(TaskName.SYNC_CHAT_PINS)[-1] == {
        "chat_id": chat_id,
        "notify": False,
        "resend": True,
    }
