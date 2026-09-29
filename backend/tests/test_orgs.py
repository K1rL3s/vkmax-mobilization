import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    OrgHouseFlatUser,
    RecordingBroker,
    add_resident,
    add_user,
    empty_bot_setup,
    make_bot_config,
    make_config,
    make_notifications_service,
)
from tests.test_admin_map import _staff_headers

from zheka.api.app import app_factory
from zheka.api.schemas.houses import OrgContacts
from zheka.api.schemas.orgs import RegisterOrgRequest, UpdateOrgSettingsRequest
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core import texts
from zheka.core.deeplinks import Deeplink, DeeplinkKind, parse_deeplink
from zheka.core.enums import (
    EventType,
    OrgRole,
    RequestCategory,
    ResidentRole,
    ResidentStatus,
)
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import MaxUserId, UserId
from zheka.core.services.demo import DEMO_LOCKED
from zheka.core.services.events import EventsService
from zheka.core.services.moderation import SPARE_CHAIRMAN, ModerationService
from zheka.core.services.orgs import OrgSettingsView, OrgsService
from zheka.infra.database.models import Event, OrgMember, Organization, User
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
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
) -> ModerationService:
    return ModerationService(
        ResidentsRepo(session),
        UsersRepo(session),
        HousesRepo(session),
        make_notifications_service(session, publisher),
        EventsService(EventsRepo(session)),
        OrgsRepo(session),
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
        ("demo_staff_1", Deeplink(kind=DeeplinkKind.DEMO_STAFF, value="1")),
        ("demo_admin_5", Deeplink(kind=DeeplinkKind.DEMO_ADMIN, value="5")),
        ("demo_executor_4", Deeplink(kind=DeeplinkKind.DEMO_EXECUTOR, value="4")),
        ("demo_executor_6", None),
        ("demo_staff", None),
        ("demo_staff_6", None),
        ("demo_resident_0", None),
        ("house_", None),
        ("wat_1", None),
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
        emergency_phone=" +79990000112 ",
        email=None,
        site=None,
    )
    assert updated.settings.meter_window_day_to == 20
    assert updated.org.reception_note == "по записи"
    assert OrgContacts.model_validate(updated.org).emergency_phone == "+79990000112"

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
    await orgs_service.revoke_invite(own.org_id, invite.code, own.user_id)
    with pytest.raises(InvalidState):
        await orgs_service.activate_invite(own.user_id, invite.code)


async def test_org_mail_and_site_reach_house_contacts(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    orgs_service = make_orgs_service(session)

    async def save(email: str | None, site: str | None) -> OrgSettingsView:
        return await orgs_service.update_settings(
            own.org_id,
            15,
            25,
            meter_window_always_open=False,
            group_threshold=3,
            group_window_hours=24,
            phone="+79990000000",
            reception_note=None,
            emergency_phone=None,
            email=email,
            site=site,
        )

    contacts = OrgContacts.model_validate(
        (await save(" Priem@UK.RU ", "www.uk.ru")).org,
    )
    assert contacts.email == "priem@uk.ru"
    assert contacts.site == "https://www.uk.ru"

    cleared = OrgContacts.model_validate((await save("  ", "")).org)
    assert cleared.email is None
    assert cleared.site is None

    with pytest.raises(InvalidRequest):
        await save("почта без собаки", None)

    with pytest.raises(InvalidRequest):
        await save(None, "не знаю")


async def test_register(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    seeded = await make_org_house_flat_user(registered=False)
    orgs_service = make_orgs_service(session)
    org = await OrgsRepo(session).get(seeded.org_id)
    assert org is not None

    with pytest.raises(NotEnoughRights):
        await orgs_service.register(
            seeded.user_id,
            "wrong",
            org.inn,
            None,
            "УК",
            "+7",
            "адрес",
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
        org_role=OrgRole.CREATOR,
        resident_role=ResidentRole.OWNER,
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
    org = await OrgsRepo(session).get(own.org_id)
    assert org is not None
    contact = texts.org_contact(org.name, org.phone)
    assert contact in blocked["text"]
    assert "вернула" in unblocked["text"]

    stmt = select(Event).order_by(events_table.c.id)
    events = (await session.execute(stmt)).scalars().all()
    assert [event.type for event in events] == [
        EventType.RESIDENT_BLOCKED,
        EventType.RESIDENT_UNBLOCKED,
    ]
    assert {event.user_id for event in events} == {own.user_id}

    with pytest.raises(InvalidState):
        await moderation.set_chairman(
            own.org_id,
            resident.id,
            value=True,
            by=own.user_id,
        )

    resident.verified_at = datetime.now(UTC)
    await session.flush()
    view = await moderation.set_chairman(
        own.org_id,
        resident.id,
        value=True,
        by=own.user_id,
    )
    assert view.resident.is_chairman is True

    with pytest.raises(InvalidState):
        await moderation.block(own.org_id, resident.id, "причина", own.user_id)

    view = await moderation.revoke_verification(
        own.org_id,
        resident.id,
        "нет подтверждения",
        own.user_id,
    )
    assert view.resident.verified_at is None
    assert view.resident.is_chairman is False

    await publisher.flush()
    revoked = broker.enqueued(TaskName.SEND_TO_USER)[-1]
    assert revoked["user_id"] == own.user_id
    assert revoked["mandatory"] is True
    assert "нет подтверждения" in revoked["text"]
    assert contact in revoked["text"]


async def test_foreign_resident_is_not_found_for_another_org(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    other = await make_org_house_flat_user(resident_role=ResidentRole.OWNER)
    foreign = await ResidentsRepo(session).get_for_house(other.user_id, other.house_id)
    assert foreign is not None

    with pytest.raises(EntityNotFound):
        await make_moderation_service(session).block(
            own.org_id,
            foreign.id,
            "причина",
            own.user_id,
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
        await orgs_service.revoke_invite(
            own.org_id,
            foreign_invite.code,
            own.user_id,
        )

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
            emergency_phone=None,
            email=None,
            site=None,
        )


@pytest.mark.parametrize(
    ("expires_in_hours", "max_activations"),
    [(0, 1), (-1, 1), (72, 0)],
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


def test_org_contact_without_a_phone_is_the_name_alone() -> None:
    assert texts.org_contact("УК Дом", " ") == "Связаться с УК: УК Дом"
    assert texts.org_contact("УК Дом", "+7 1") == "Связаться с УК: УК Дом, +7 1"


async def test_a_member_cannot_rise_on_a_used_up_invite(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
) -> None:
    org = await make_org_house_flat_user(org_role=OrgRole.CREATOR)
    admin = await make_org_house_flat_user()
    employee = await make_org_house_flat_user()
    orgs_service = make_orgs_service(session)

    async def invite(role: OrgRole) -> str:
        created = await orgs_service.create_invite(
            org.org_id,
            org.user_id,
            OrgRole.CREATOR,
            role,
            expires_in_hours=72,
            max_activations=1,
        )
        return created.code

    admin_code = await invite(OrgRole.ADMIN)
    await orgs_service.activate_invite(employee.user_id, await invite(OrgRole.EMPLOYEE))
    await orgs_service.activate_invite(admin.user_id, admin_code)
    await orgs_service.activate_invite(admin.user_id, admin_code)

    with pytest.raises(InvalidState):
        await orgs_service.activate_invite(employee.user_id, admin_code)

    member = await OrgsRepo(session).get_member(org.org_id, employee.user_id)
    assert member is not None
    assert member.role is OrgRole.EMPLOYEE


@pytest.mark.parametrize("action", ["block", "revoke_verification"])
@pytest.mark.parametrize(
    ("max_user_id", "spared"),
    [(MaxUserId(7), True), (MaxUserId(-7), False)],
    ids=["reviewer", "seeded"],
)
async def test_a_demo_org_restricts_only_seeded_residents(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
    action: str,
    max_user_id: MaxUserId,
    spared: bool,
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    org = await OrgsRepo(session).get(own.org_id)
    assert org is not None
    org.is_demo = True
    user = User(max_user_id=max_user_id, name="Сосед")
    session.add(user)
    await session.flush()
    resident = await add_resident(session, user.id, own.house_id, own.flat_id)
    restrict = getattr(make_moderation_service(session), action)

    if spared:
        with pytest.raises(NotEnoughRights):
            await restrict(own.org_id, resident.id, "причина", own.user_id)
    else:
        await restrict(own.org_id, resident.id, "причина", own.user_id)


async def test_a_blank_emergency_phone_is_cleared(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    updated = await make_orgs_service(session).update_settings(
        own.org_id,
        15,
        25,
        meter_window_always_open=False,
        group_threshold=3,
        group_window_hours=24,
        phone="+79990000000",
        reception_note=None,
        emergency_phone="   ",
        email=None,
        site=None,
    )

    assert updated.org.emergency_phone is None


def _settings(phone: str, emergency_phone: str) -> UpdateOrgSettingsRequest:
    return UpdateOrgSettingsRequest(
        meter_window_day_from=15,
        meter_window_day_to=25,
        meter_window_always_open=False,
        group_threshold=3,
        group_window_hours=24,
        phone=phone,
        emergency_phone=emergency_phone,
    )


def _registration(phone: str) -> RegisterOrgRequest:
    return RegisterOrgRequest(
        deeplink_code="code",
        inn="7700000000",
        name="УК",
        phone=phone,
        address="Москва",
    )


@pytest.mark.parametrize(
    "build",
    [
        lambda phone: _settings(phone, "+79990000112"),
        lambda phone: _settings("+79990000000", phone),
        _registration,
    ],
)
def test_an_org_phone_is_capped(build: Callable[[str], object]) -> None:
    build("7" * 32)

    with pytest.raises(ValidationError):
        build("7" * 33)


@pytest.mark.parametrize("is_demo", [True, False], ids=["demo", "live"])
@pytest.mark.parametrize(
    "action",
    ["settings", "member", "category_executor", "reception"],
)
async def test_a_demo_org_keeps_its_setup(
    bot_session: AsyncSession,
    action: str,
    is_demo: bool,
) -> None:
    headers, colleague_id = await _admin_with_colleague(bot_session, is_demo=is_demo)
    requests: dict[str, tuple[str, str, object]] = {
        "settings": (
            "PUT",
            "/api/admin/org/settings",
            _settings("+79990000000", "").model_dump(mode="json"),
        ),
        "member": ("DELETE", f"/api/admin/org/members/{colleague_id}", None),
        "category_executor": (
            "PUT",
            "/api/admin/org/category-executors",
            {"category": RequestCategory.LEAK, "executor_user_id": None},
        ),
        "reception": ("PUT", "/api/admin/reception/windows", {"windows": []}),
    }
    method, url, body = requests[action]

    async with _client() as client:
        response = await client.request(method, url, headers=headers, json=body)

    if is_demo:
        assert response.status_code == 403
        assert response.json()["error"]["detail"] == DEMO_LOCKED
    else:
        assert response.status_code == 200


@pytest.mark.parametrize("is_demo", [True, False], ids=["demo", "live"])
async def test_a_demo_org_offers_no_one_to_remove(
    bot_session: AsyncSession,
    is_demo: bool,
) -> None:
    headers, colleague_id = await _admin_with_colleague(bot_session, is_demo=is_demo)

    async with _client() as client:
        response = await client.get("/api/admin/org/members", headers=headers)

    can_remove = {item["user_id"]: item["can_remove"] for item in response.json()}
    assert can_remove[colleague_id] is not is_demo


@pytest.mark.parametrize(
    ("is_demo", "own_invite", "revoked"),
    [(True, False, False), (True, True, True), (False, False, True)],
    ids=["demo-foreign", "demo-own", "live-foreign"],
)
async def test_a_demo_org_admin_revokes_only_own_invites(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    is_demo: bool,
    own_invite: bool,
    revoked: bool,
) -> None:
    await _mark_demo(session, own, is_demo=is_demo)
    colleague_id = await add_user(session)
    orgs_service = make_orgs_service(session)
    invite = await orgs_service.create_invite(
        own.org_id,
        own.user_id if own_invite else colleague_id,
        OrgRole.ADMIN,
        OrgRole.EMPLOYEE,
        expires_in_hours=72,
        max_activations=1,
    )

    if revoked:
        await orgs_service.revoke_invite(own.org_id, invite.code, own.user_id)
    else:
        with pytest.raises(NotEnoughRights, match=DEMO_LOCKED):
            await orgs_service.revoke_invite(own.org_id, invite.code, own.user_id)

    stored = await InvitesRepo(session).get(invite.code)
    assert stored is not None
    assert (stored.revoked_at is not None) is revoked


@pytest.mark.parametrize("appoint", [True, False], ids=["replace", "remove"])
@pytest.mark.parametrize(
    ("sign", "spared"),
    [(1, True), (-1, False)],
    ids=["reviewer", "seeded"],
)
async def test_a_demo_org_keeps_a_reviewer_chairman(
    session: AsyncSession,
    make_org_house_flat_user: Callable[..., Awaitable[OrgHouseFlatUser]],
    appoint: bool,
    sign: int,
    spared: bool,
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    await _mark_demo(session, own, is_demo=True)
    successor = await add_resident(session, own.user_id, own.house_id, own.flat_id)
    holder = User(max_user_id=MaxUserId(sign * secrets.randbits(40)), name="Сосед")
    session.add(holder)
    await session.flush()
    chairman = await add_resident(
        session,
        holder.id,
        own.house_id,
        own.flat_id,
        is_chairman=True,
    )
    target = successor if appoint else chairman
    moderation = make_moderation_service(session)

    if spared:
        with pytest.raises(NotEnoughRights, match=SPARE_CHAIRMAN):
            await moderation.set_chairman(
                own.org_id,
                target.id,
                value=appoint,
                by=own.user_id,
            )
    else:
        await moderation.set_chairman(
            own.org_id,
            target.id,
            value=appoint,
            by=own.user_id,
        )

    await session.refresh(chairman)
    assert chairman.is_chairman is spared


async def _admin_with_colleague(
    session: AsyncSession,
    *,
    is_demo: bool,
) -> tuple[dict[str, str], UserId]:
    org = Organization(
        name=f"УК {secrets.token_hex(4)}",
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Тестовая область, Тестоград, Тестовая, 1",
        registered_at=datetime.now(UTC),
        timezone="Europe/Moscow",
        is_demo=is_demo,
    )
    session.add(org)
    await session.flush()
    org_id = org.id
    headers = await _staff_headers(session, org_id, OrgRole.ADMIN)
    colleague_id = await add_user(session)
    session.add(OrgMember(org_id=org_id, user_id=colleague_id, role=OrgRole.EMPLOYEE))
    await session.commit()
    return headers, colleague_id


def _client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app_factory(make_bot_config(), empty_bot_setup())),
        base_url="http://test",
    )


async def _mark_demo(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    *,
    is_demo: bool,
) -> None:
    org = await OrgsRepo(session).get(own.org_id)
    assert org is not None
    org.is_demo = is_demo
    await session.flush()
