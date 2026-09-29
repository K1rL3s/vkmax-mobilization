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
from tests.test_requests import _complain
from tests.test_residency import _profile_service

from zheka.api.dependencies.current_account import CurrentAccount
from zheka.api.routes.me import verify_phone
from zheka.api.schemas.houses import HouseResidentItem
from zheka.api.schemas.me import MeResponse, VerifyPhoneRequest
from zheka.api.schemas.requests import AdminRequestCard
from zheka.core.contact import BAD_CONTACT, verify_bridge_contact
from zheka.core.enums import EventType
from zheka.core.errors import InvalidRequest
from zheka.core.services.houses import HouseResidentView
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
    assert AdminRequestCard.of_admin(card, [], []).author_phone == "+79991234567"
    resident = (await ResidentsRepo(session).list_for_user(own.user_id))[0]
    item = HouseResidentItem.of(
        HouseResidentView(resident=resident, user=user, flat=None),
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
