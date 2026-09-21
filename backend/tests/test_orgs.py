from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    OrgHouseFlatUser,
    RecordingBroker,
    make_config,
    make_notifications_service,
)

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.deeplinks import Deeplink, DeeplinkKind, parse_deeplink
from zheka.core.enums import EventType, OrgRole, ResidentRole, ResidentStatus
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.services.events import EventsService
from zheka.core.services.moderation import ModerationService
from zheka.core.services.orgs import OrgsService
from zheka.infra.database.models import Event
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.invites import InvitesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.events import events_table


def make_orgs_service(session: AsyncSession) -> OrgsService:
    return OrgsService(
        OrgsRepo(session),
        InvitesRepo(session),
        HousesRepo(session),
        UsersRepo(session),
        EventsService(EventsRepo(session)),
        make_config().deeplinks,
    )


def make_moderation_service(
    session: AsyncSession, publisher: TaskPublisher | None = None
) -> ModerationService:
    return ModerationService(
        ResidentsRepo(session),
        UsersRepo(session),
        HousesRepo(session),
        make_notifications_service(session, publisher),
        EventsService(EventsRepo(session)),
    )


async def test_single_use_invite_is_not_activated_twice(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    org = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    first = await make_org_house_flat_user()
    second = await make_org_house_flat_user()
    orgs_service = make_orgs_service(session)

    invite = await orgs_service.create_invite(
        org.org_id,
        org.user_id,
        OrgRole.CREATOR,
        OrgRole.EMPLOYEE,
        expires_in_hours=72,
        max_activations=1,
    )
    await orgs_service.activate_invite(first.user_id, invite.code)

    with pytest.raises(InvalidState):
        await orgs_service.activate_invite(second.user_id, invite.code)

    used = await InvitesRepo(session).get(invite.code)
    assert used is not None
    assert used.activations_used == 1
    assert await OrgsRepo(session).get_member(org.org_id, second.user_id) is None


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("reg_secret", Deeplink(kind=DeeplinkKind.ORG_REGISTER, value="secret")),
        ("qr_12_3", Deeplink(kind=DeeplinkKind.ENTRANCE_QR, value="12_3")),
        ("demo_staff", Deeplink(kind=DeeplinkKind.DEMO_STAFF)),
        ("house_", None),
        ("wat_1", None),
        ("", None),
    ],
)
def test_parse_deeplink(payload: str, expected: Deeplink | None) -> None:
    assert parse_deeplink(payload) == expected


async def test_org_surface(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    orgs_service = make_orgs_service(session)
    org = await OrgsRepo(session).get(own.org_id)
    assert org is not None

    lookup = await orgs_service.lookup(org.inn, None)
    assert lookup.org is not None
    assert len(lookup.houses) == 1

    card = await orgs_service.card(own.org_id)
    assert card.houses_count == 1
    assert card.members_count == 1

    settings = await orgs_service.settings(own.org_id)
    assert settings.settings.meter_window_day_from == 15

    updated = await orgs_service.update_settings(
        own.org_id,
        10,
        20,
        meter_window_always_open=True,
        group_threshold=2,
        group_window_hours=24,
        phone="+79990000000",
        reception_note="по записи",
    )
    assert updated.settings.meter_window_day_to == 20
    assert updated.org.reception_note == "по записи"

    members = await orgs_service.members(own.org_id)
    assert len(members) == 1

    with pytest.raises(NotEnoughRights):
        await orgs_service.remove_member(own.org_id, OrgRole.CREATOR, own.user_id)

    invite = await orgs_service.create_invite(
        own.org_id,
        own.user_id,
        OrgRole.ADMIN,
        OrgRole.EMPLOYEE,
        expires_in_hours=1,
        max_activations=2,
    )
    assert len(await orgs_service.invites(own.org_id)) == 1
    await orgs_service.revoke_invite(own.org_id, invite.code)
    with pytest.raises(InvalidState):
        await orgs_service.activate_invite(own.user_id, invite.code)


async def test_register(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    seeded = await make_org_house_flat_user()
    orgs_service = make_orgs_service(session)
    org = await OrgsRepo(session).get(seeded.org_id)
    assert org is not None

    with pytest.raises(NotEnoughRights):
        await orgs_service.register(
            seeded.user_id, "wrong", org.inn, None, "УК", "+7", "адрес"
        )

    card = await orgs_service.register(
        seeded.user_id,
        "test-register-code",
        org.inn,
        None,
        "УК Новая",
        "+79990000000",
        "новый адрес",
    )
    assert card.org.registered_at is not None
    assert card.members_count == 1

    with pytest.raises(InvalidState):
        await orgs_service.register(
            seeded.user_id,
            "test-register-code",
            org.inn,
            None,
            "УК Новая",
            "+79990000000",
            "новый адрес",
        )


async def test_moderation(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    own = await make_org_house_flat_user(
        org_role=OrgRole.CREATOR, resident_role=ResidentRole.OWNER
    )
    resident = await ResidentsRepo(session).get_for_house(own.user_id, own.house_id)
    assert resident is not None
    moderation = make_moderation_service(session, publisher)

    view = await moderation.block(own.org_id, resident.id, "  мусорит  ", own.user_id)
    assert view.resident.status is ResidentStatus.BLOCKED
    assert view.resident.block_reason == "мусорит"

    view = await moderation.unblock(own.org_id, resident.id, own.user_id)
    assert view.resident.status is ResidentStatus.ACTIVE

    await publisher.flush()
    blocked, unblocked = broker.enqueued(TaskName.SEND_TO_USER)
    assert blocked["user_id"] == unblocked["user_id"] == own.user_id
    assert blocked["mandatory"] is unblocked["mandatory"] is True
    assert "мусорит" in blocked["text"]
    assert "вернула" in unblocked["text"]

    # в строке жителя нет ни автора, ни времени блокировки, след - только событие
    stmt = select(Event).order_by(events_table.c.id)
    events = (await session.execute(stmt)).scalars().all()
    assert [event.type for event in events] == [
        EventType.RESIDENT_BLOCKED,
        EventType.RESIDENT_UNBLOCKED,
    ]
    assert {event.user_id for event in events} == {own.user_id}

    with pytest.raises(InvalidState):
        await moderation.set_chairman(own.org_id, resident.id, value=True)

    resident.verified_at = datetime.now(UTC)
    await session.flush()
    view = await moderation.set_chairman(own.org_id, resident.id, value=True)
    assert view.resident.is_chairman is True

    with pytest.raises(InvalidState):
        await moderation.block(own.org_id, resident.id, "причина", own.user_id)

    view = await moderation.revoke_verification(
        own.org_id, resident.id, "нет подтверждения", own.user_id
    )
    assert view.resident.verified_at is None
    # председателем бывает только подтвержденный житель
    assert view.resident.is_chairman is False


async def test_foreign_resident_is_not_found_for_another_org(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await ResidentsRepo(session).get_for_house(other.user_id, other.house_id)
    assert foreign is not None

    # _get_resident общий для всей модерации. 404, а не 403: 403 подтвердил бы,
    # что такой resident_id существует
    with pytest.raises(EntityNotFound):
        await make_moderation_service(session).block(
            own.org_id, foreign.id, "причина", own.user_id
        )


async def test_foreign_invite_is_not_revoked_from_another_org(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    other = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    orgs_service = make_orgs_service(session)
    foreign_invite = await orgs_service.create_invite(
        other.org_id,
        other.user_id,
        OrgRole.CREATOR,
        OrgRole.EMPLOYEE,
        expires_in_hours=72,
        max_activations=1,
    )

    with pytest.raises(EntityNotFound):
        await orgs_service.revoke_invite(own.org_id, foreign_invite.code)

    alive = await InvitesRepo(session).get(foreign_invite.code)
    assert alive is not None
    assert alive.revoked_at is None


@pytest.mark.parametrize(
    ("day_from", "day_to", "group_threshold", "group_window_hours"),
    [
        (0, 25, 3, 24),
        (15, 29, 3, 24),
        (15, 25, 1, 24),
        (15, 25, 3, 0),
        (15, 25, 3, 169),
    ],
)
async def test_update_settings_rejects_values_outside_the_limits(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
    day_from: int,
    day_to: int,
    group_threshold: int,
    group_window_hours: int,
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.CREATOR)

    with pytest.raises(InvalidRequest):
        await make_orgs_service(session).update_settings(
            own.org_id,
            day_from,
            day_to,
            meter_window_always_open=False,
            group_threshold=group_threshold,
            group_window_hours=group_window_hours,
            phone="+79990000000",
            reception_note=None,
        )


@pytest.mark.parametrize(
    ("expires_in_hours", "max_activations"), [(0, 1), (-1, 1), (72, 0)]
)
async def test_create_invite_rejects_dead_limits(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
    expires_in_hours: int,
    max_activations: int,
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.CREATOR)

    with pytest.raises(InvalidRequest):
        await make_orgs_service(session).create_invite(
            own.org_id,
            own.user_id,
            OrgRole.CREATOR,
            OrgRole.EMPLOYEE,
            expires_in_hours=expires_in_hours,
            max_activations=max_activations,
        )
