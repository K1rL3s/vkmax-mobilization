import hashlib
import hmac
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from maxo.utils.webapp import WebAppChat, WebAppInitData, WebAppUser
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    OrgHouseFlatUser,
    admin_requests_service,
    events_of,
    make_config,
)
from tests.test_houses import _make_service
from tests.test_requests import _complain, _group_of_three
from tests.test_residency import _profile_service

from zheka.api.dependencies.current_account import CurrentAccount
from zheka.api.dependencies.current_org import CurrentOrg
from zheka.api.routes.admin.houses import list_house_residents
from zheka.api.routes.admin.requests import (
    get_org_request,
    get_request_group,
    list_org_requests,
)
from zheka.api.routes.me import verify_phone
from zheka.api.schemas.houses import HouseResidentItem
from zheka.api.schemas.me import MeResponse, VerifyPhoneRequest
from zheka.api.schemas.requests import AdminRequestCard
from zheka.core.contact import BAD_CONTACT, verify_bridge_contact
from zheka.core.enums import EventType, OrgRole
from zheka.core.errors import InvalidRequest
from zheka.core.ids import UserId
from zheka.core.services.files import FilesService
from zheka.core.services.houses import HouseResidentView
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

TOKEN = "bot-token"  # noqa: S105
NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
USER = 4242


def _signed(phone: str, auth_date: str, user: int = USER, token: str = TOKEN) -> str:
    data = f"authDate={auth_date}\nphone={phone.removeprefix('+')}\nuserId={user}"
    return hmac.new(token.encode(), data.encode(), hashlib.sha256).hexdigest()


@pytest.mark.parametrize(
    "auth_date",
    [str(int(NOW.timestamp()) - 60), str(int(NOW.timestamp() * 1000) - 60_000)],
    ids=["seconds", "milliseconds"],
)
def test_a_contact_signed_by_the_bot_token_gives_the_phone(auth_date: str) -> None:
    signature = _signed("79991234567", auth_date).upper()

    phone = verify_bridge_contact(
        "+79991234567",
        auth_date,
        signature,
        USER,
        TOKEN,
        NOW,
    )

    assert phone == "+79991234567"


@pytest.mark.parametrize(
    ("auth_date", "signature"),
    [
        ("1790000000", _signed("79991234567", "1790000000", user=USER + 1)),
        ("1790000000", _signed("79991234567", "1790000000", token="x")),  # noqa: S106
        (
            str(int((NOW - timedelta(days=2)).timestamp())),
            _signed("79991234567", str(int((NOW - timedelta(days=2)).timestamp()))),
        ),
        (
            str(int((NOW + timedelta(hours=1)).timestamp())),
            _signed("79991234567", str(int((NOW + timedelta(hours=1)).timestamp()))),
        ),
        ("1790000000", "0" * 64),
        ("1790000000", "ж" * 64),
    ],
    ids=["other_user", "other_token", "stale", "future", "forged", "not_hex"],
)
def test_a_contact_not_signed_for_this_user_now_is_refused(
    auth_date: str,
    signature: str,
) -> None:
    with pytest.raises(InvalidRequest, match=BAD_CONTACT):
        verify_bridge_contact("79991234567", auth_date, signature, USER, TOKEN, NOW)


async def test_a_phone_is_kept_shown_to_staff_and_forgotten(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = _profile_service(session)
    request = await _complain(session, own.user_id, own.house_id)

    await service.set_phone(own.user_id, "+79991234567")
    view = await service.set_phone(own.user_id, "+79991234567")

    assert MeResponse.of(view).phone == "+79991234567"
    user = await UsersRepo(session).get_by_id(own.user_id)
    assert user is not None
    assert user.phone_verified_at is not None
    card = await admin_requests_service(session).card(own.org_id, request.id)
    staff = _viewer(own, UserId(0), is_demo=False)
    assert AdminRequestCard.of_admin(card, [], [], staff).author_phone == "+79991234567"
    resident = (await ResidentsRepo(session).list_for_user(own.user_id))[0]
    item = HouseResidentItem.of(
        HouseResidentView(resident=resident, user=user, flat=None),
        staff,
    )
    assert item.phone == "+79991234567"

    await service.set_phone(own.user_id, None)
    await service.set_phone(own.user_id, None)

    session.expire_all()
    cleared = await UsersRepo(session).get_by_id(own.user_id)
    assert cleared is not None
    assert (cleared.phone, cleared.phone_verified_at) == (None, None)
    assert len(await events_of(session, EventType.PHONE_VERIFIED)) == 1
    assert len(await events_of(session, EventType.PHONE_FORGOTTEN)) == 1


async def test_forgetting_the_account_drops_the_phone(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    service = _profile_service(session)
    await service.set_phone(own.user_id, "+79991234567")

    await service.forget(own.user_id)

    user = await UsersRepo(session).get_by_id(own.user_id)
    assert user is not None
    assert (user.phone, user.phone_verified_at) == (None, None)


async def test_the_route_checks_the_signature_of_the_current_max_user(
    session: AsyncSession,
    own: OrgHouseFlatUser,
) -> None:
    user = await UsersRepo(session).get_by_id(own.user_id)
    assert user is not None
    config = make_config()
    auth_date = str(int(datetime.now(UTC).timestamp()))
    account = CurrentAccount(user_id=own.user_id, consent_at=datetime.now(UTC))
    webapp = WebAppInitData(
        chat=WebAppChat(id=user.max_user_id, type="DIALOG"),
        user=WebAppUser(id=user.max_user_id, first_name="Житель"),
        hash="",
    )
    signed = _signed("79991234567", auth_date, user.max_user_id, config.max.token)
    body = VerifyPhoneRequest(phone="+79991234567", auth_date=auth_date, hash=signed)

    me = await verify_phone(account, webapp, body, config, _profile_service(session))

    assert me.phone == "+79991234567"
    stranger = replace(webapp, user=WebAppUser(id=user.max_user_id + 1, first_name="Ж"))
    with pytest.raises(InvalidRequest):
        await verify_phone(account, stranger, body, config, _profile_service(session))


def _viewer(own: OrgHouseFlatUser, user_id: UserId, *, is_demo: bool) -> CurrentOrg:
    return CurrentOrg(
        org_id=own.org_id,
        user_id=user_id,
        role=OrgRole.ADMIN,
        is_demo=is_demo,
    )


@pytest.mark.parametrize("endpoint", ["list", "card", "group", "residents"])
@pytest.mark.parametrize(
    ("is_demo", "by_owner", "seen"),
    [(True, False, None), (True, True, "+79991234567"), (False, False, "+79991234567")],
    ids=["demo_stranger", "demo_owner", "real_staff"],
)
async def test_a_demo_org_shows_a_phone_only_to_its_owner(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    endpoint: str,
    is_demo: bool,
    by_owner: bool,
    seen: str | None,
) -> None:
    members, group_id = await _group_of_three(session, own)
    request = members[0]
    assert request.author_user_id is not None
    author = await UsersRepo(session).get_by_id(request.author_user_id)
    assert author is not None
    await UsersRepo(session).set_phone(author, "+79991234567", datetime.now(UTC))
    (await OrgsRepo(session).get_existing(own.org_id)).is_demo = is_demo
    await session.flush()
    viewer = _viewer(own, author.id if by_owner else own.user_id, is_demo=is_demo)
    service = admin_requests_service(session)

    if endpoint == "list":
        page = await list_org_requests(viewer, service, house_id=own.house_id)
        phones = [item.author_phone for item in page.items if item.id == request.id]
    elif endpoint == "card":
        files = FilesService(make_config().files, "test-token")
        card = await get_org_request(request.id, viewer, service, files)
        phones = [card.author_phone]
    elif endpoint == "group":
        group = await get_request_group(group_id, viewer, service)
        phones = [item.author_phone for item in group.requests if item.id == request.id]
    else:
        residents = await list_house_residents(
            own.house_id,
            viewer,
            _make_service(session),
        )
        phones = [item.phone for item in residents.items if item.user_id == author.id]

    assert phones == [seen]
