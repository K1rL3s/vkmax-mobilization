import json
import secrets
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from maxo.dialogs.test_tools.bot_client import FakeBot
from maxo.utils.deeplink import create_start_link
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    OrgHouseFlatUser,
    RecordingBroker,
    make_bot_config,
    make_notifications_service,
    signed_init_data,
)
from tests.test_auth import CHECKER_TOKEN, _app
from tests.test_bot import _bot_house
from tests.test_escalation import _open_dialog

from zheka.api.dependencies.current_residency import CurrentResidency
from zheka.api.routes.houses import get_neighbour_invite
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.consent import CONSENT_VERSION
from zheka.core.deeplinks import Deeplink, DeeplinkKind, parse_deeplink
from zheka.core.enums import EventSource
from zheka.core.errors import InvalidState
from zheka.core.services.neighbour_invite import NeighbourInviteService
from zheka.core.texts import neighbour_invite_text
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.users import UsersRepo


def _service(
    session: AsyncSession,
    publisher: TaskPublisher | None = None,
) -> NeighbourInviteService:
    return NeighbourInviteService(
        HousesRepo(session),
        OrgsRepo(session),
        UsersRepo(session),
        make_notifications_service(session, publisher),
    )


def _residency(own: OrgHouseFlatUser) -> CurrentResidency:
    return CurrentResidency(
        user_id=own.user_id,
        house_id=own.house_id,
        flat_id=own.flat_id,
        can_see_charges=False,
        verified=False,
    )


@pytest.mark.parametrize("registered", [True, False])
async def test_a_neighbour_invite_is_a_bot_link_into_the_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    fake_bot: FakeBot,
    registered: bool,
) -> None:
    own = await make_org_house_flat_user(registered=registered)

    invite = await get_neighbour_invite(
        own.house_id,
        _residency(own),
        _service(session),
        fake_bot,
    )

    house = await HousesRepo(session).get(own.house_id)
    assert house is not None
    payload = f"nb_{own.house_id}"
    assert invite.link == create_start_link(fake_bot, payload)
    assert invite.is_connected is registered
    assert invite.text == neighbour_invite_text(house.address, connected=registered)
    deeplink = parse_deeplink(payload)
    assert deeplink == Deeplink(
        kind=DeeplinkKind.NEIGHBOUR_INVITE,
        value=str(own.house_id),
    )
    assert deeplink.source is EventSource.INVITE


def test_the_invite_text_tells_a_house_without_its_uk_to_call_it() -> None:
    assert neighbour_invite_text("Казань, Баумана, 12", connected=True) == (
        "Наш дом Казань, Баумана, 12 в Жэке: заявки в УК, объявления и показания "
        "в MAX. Дом уже выбран, укажите квартиру:"
    )
    assert neighbour_invite_text("Казань, Баумана, 12", connected=False) == (
        "Зовем нашу УК в Жэку. Присоединяйтесь, дом Казань, Баумана, 12 уже выбран:"
    )


async def test_a_leaflet_goes_to_a_resident_the_bot_can_write_to(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    await _open_dialog(session, own.user_id)

    await _service(session, publisher).send_leaflet(own.user_id, own.house_id)

    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_NEIGHBOUR_LEAFLET) == [
        {"user_id": own.user_id, "house_id": own.house_id},
    ]


async def test_a_leaflet_is_refused_when_the_bot_cannot_write(
    session: AsyncSession,
    own: OrgHouseFlatUser,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    with pytest.raises(InvalidState, match="Бот не может вам написать"):
        await _service(session, publisher).send_leaflet(own.user_id, own.house_id)

    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_NEIGHBOUR_LEAFLET) == []


async def test_only_a_resident_of_the_house_gets_its_invite_and_leaflet(
    bot_session: AsyncSession,
) -> None:
    house_id, _address = await _bot_house(bot_session)
    app = _app(CHECKER_TOKEN, make_bot_config().db)
    max_user = json.dumps({"id": secrets.randbits(40), "first_name": "Жека"})
    stranger = {"WebAppData": signed_init_data(datetime.now(UTC), user=max_user)}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/me/consent",
            headers=stranger,
            json={"version": CONSENT_VERSION},
        )
        invite = await client.get(
            f"/api/houses/{house_id}/neighbour-invite",
            headers=stranger,
        )
        leaflet = await client.post(
            f"/api/houses/{house_id}/neighbour-invite/leaflet",
            headers=stranger,
        )

    assert (invite.status_code, leaflet.status_code) == (404, 404)
