import secrets
from collections.abc import Awaitable, Callable
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser

from zheka.api.dependencies.current_org import resolve_org
from zheka.core.enums import (
    EventType,
    OrgRole,
    RequestCategory,
    RequestChannel,
    RequestStatus,
)
from zheka.core.errors import NotEnoughRights
from zheka.core.ids import HouseId, MaxUserId, OrgId, RequestId, UserId
from zheka.core.services.access import can_invite, can_remove_member
from zheka.core.services.events import EventsService
from zheka.infra.database.models import Event, OrgMember, Request, User
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.scopes import scoped_to_org
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.requests import requests_table


async def _add_request(session: AsyncSession, house_id: HouseId) -> RequestId:
    request = Request(
        house_id=house_id,
        category=RequestCategory.OTHER,
        description="Тестовая заявка",
        status=RequestStatus.NEW,
        channel=RequestChannel.MINIAPP,
    )
    session.add(request)
    await session.flush()
    return request.id


async def test_scoped_to_org_hides_foreign_request(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    org_a = await make_org_house_flat_user()
    org_b = await make_org_house_flat_user()
    foreign_request_id = await _add_request(session, org_b.house_id)

    stmt = scoped_to_org(
        select(Request),
        requests_table.c.house_id,
        org_a.org_id,
    ).where(requests_table.c.id == foreign_request_id)
    result = await session.execute(stmt)

    assert result.scalar_one_or_none() is None


async def test_scoped_to_org_lists_only_own_org(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    org_a = await make_org_house_flat_user()
    org_b = await make_org_house_flat_user()
    own_request_id = await _add_request(session, org_a.house_id)
    await _add_request(session, org_b.house_id)

    stmt = scoped_to_org(select(Request), requests_table.c.house_id, org_a.org_id)
    result = await session.execute(stmt)

    assert [row.id for row in result.scalars().all()] == [own_request_id]


def test_resolve_org_rejects_org_without_membership() -> None:
    membership = OrgMember(org_id=OrgId(1), user_id=UserId(1), role=OrgRole.ADMIN)

    with pytest.raises(NotEnoughRights):
        resolve_org([membership], UserId(1), org_id_header=OrgId(2))


def test_resolve_org_infers_single_membership() -> None:
    membership = OrgMember(org_id=OrgId(7), user_id=UserId(1), role=OrgRole.ADMIN)

    result = resolve_org([membership], UserId(1), org_id_header=None)

    assert result.org_id == 7


def test_resolve_org_requires_header_for_multiple_memberships() -> None:
    memberships = [
        OrgMember(org_id=OrgId(1), user_id=UserId(1), role=OrgRole.ADMIN),
        OrgMember(org_id=OrgId(2), user_id=UserId(1), role=OrgRole.EMPLOYEE),
    ]

    with pytest.raises(NotEnoughRights):
        resolve_org(memberships, UserId(1), org_id_header=None)


def test_resolve_org_rejects_executor() -> None:
    membership = OrgMember(org_id=OrgId(1), user_id=UserId(1), role=OrgRole.EXECUTOR)

    with pytest.raises(NotEnoughRights):
        resolve_org([membership], UserId(1), org_id_header=None)


async def test_upsert_by_max_id_updates_existing_row(session: AsyncSession) -> None:
    users_repo = UsersRepo(session)
    max_user_id = MaxUserId(secrets.randbits(48))

    first = await users_repo.upsert_by_max_id(max_user_id, "Иван", "ivan")
    second = await users_repo.upsert_by_max_id(
        max_user_id,
        "Иван Переименованный",
        None,
    )

    assert second.id == first.id
    assert second.name == "Иван Переименованный"
    assert second.username is None


async def test_events_service_record_swallows_write_failure(
    session: AsyncSession,
) -> None:
    events_service = EventsService(EventsRepo(session))

    # бизнес-объект добавлен до record() - savepoint не должен потерять его
    # при откате: это как раз случай, который тихо ломается при регрессии
    pending_user = User(
        max_user_id=MaxUserId(secrets.randbits(48)), name="До сбоя события"
    )
    session.add(pending_user)

    # user_id, которого нет в базе - нарушение внешнего ключа events.user_id
    await events_service.record(EventType.MINIAPP_OPEN, user_id=UserId(999_999_999))

    events = (await session.execute(select(Event))).scalars().all()
    assert events == []

    await session.flush()
    assert pending_user.id is not None


async def test_events_service_record_serializes_decimal_payload(
    session: AsyncSession,
) -> None:
    events_service = EventsService(EventsRepo(session))

    # payload может получить Decimal/datetime из значений, которые вызывающий
    # код не приводит к JSON заранее - record() должен превратить их в строку,
    # а не упасть
    await events_service.record(EventType.MINIAPP_OPEN, amount=Decimal("10.00"))

    # сессия должна остаться пригодной для обычной работы
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name="После сериализации")
    session.add(user)
    await session.flush()

    assert user.id is not None

    event = (await session.execute(select(Event))).scalars().one()
    assert event.payload == {"amount": "10.00"}


@pytest.mark.parametrize(
    ("actor_role", "target_role", "expected"),
    [
        (OrgRole.ADMIN, OrgRole.ADMIN, False),
        (OrgRole.CREATOR, OrgRole.ADMIN, True),
        (OrgRole.CREATOR, OrgRole.CREATOR, False),
        (OrgRole.ADMIN, OrgRole.CREATOR, False),
    ],
)
def test_can_remove_member(
    actor_role: OrgRole,
    target_role: OrgRole,
    expected: bool,
) -> None:
    assert can_remove_member(actor_role, target_role) is expected


@pytest.mark.parametrize(
    ("actor_role", "target_role", "expected"),
    [
        (OrgRole.CREATOR, OrgRole.CREATOR, False),
        (OrgRole.CREATOR, OrgRole.ADMIN, True),
        (OrgRole.ADMIN, OrgRole.ADMIN, False),
        (OrgRole.ADMIN, OrgRole.EMPLOYEE, True),
        (OrgRole.ADMIN, OrgRole.EXECUTOR, True),
        (OrgRole.EMPLOYEE, OrgRole.EXECUTOR, False),
        (OrgRole.EXECUTOR, OrgRole.EXECUTOR, False),
    ],
)
def test_can_invite(
    actor_role: OrgRole,
    target_role: OrgRole,
    expected: bool,
) -> None:
    assert can_invite(actor_role, target_role) is expected
