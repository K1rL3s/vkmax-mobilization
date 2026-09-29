import json
import os
import secrets
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from maxo import Bot
from maxo.dialogs import BgManagerFactory
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    add_meter,
    add_resident,
    add_tariff,
    events_of,
    make_bot_config,
    photo_name,
    signed_init_data,
)
from tests.test_auth import CHECKER_TOKEN, _app
from tests.test_requests import _complain
from tests.test_residency import _profile_service

from zheka.config import FilesConfig
from zheka.core.consent import CONSENT_VERSION
from zheka.core.enums import (
    AppointmentStatus,
    EventType,
    NotificationCategory,
    OrgRole,
    RequestAttachmentKind,
    ResidentStatus,
    TariffZone,
)
from zheka.core.errors import NotEnoughRights
from zheka.core.ids import API_CHECKER_MAX_USER_ID
from zheka.core.services.files import FilesService
from zheka.core.services.profile import CHECKER_CANNOT_FORGET, CREATOR_CANNOT_FORGET
from zheka.core.services.retention import ATTACHMENT_TTL, RetentionService
from zheka.infra.database.repos.files import FilesRepo
from zheka.infra.database.repos.idempotency import IdempotencyRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.notifications import NotificationsRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.reception import ReceptionRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import FORGOTTEN_NAME, UsersRepo
from zheka.infra.database.tables.houses import houses_table
from zheka.infra.database.tables.requests import requests_table
from zheka.infra.max import MaxSender


async def test_a_forgotten_user_keeps_the_request_but_not_the_name_or_the_max_id(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.EMPLOYEE)
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    request = await _complain(session, own.user_id, own.house_id)
    residents = ResidentsRepo(session)
    for resident in await residents.list_for_user(own.user_id):
        resident.status = ResidentStatus.BLOCKED
    users = UsersRepo(session)
    await users.set_consent(own.user_id, CONSENT_VERSION)
    user = await users.get_by_id(own.user_id)
    assert user is not None
    old_max_id = user.max_user_id

    await _profile_service(session).forget(own.user_id)

    assert user.name == FORGOTTEN_NAME
    assert user.max_user_id < API_CHECKER_MAX_USER_ID
    assert user.consent_at is None
    assert await users.get_by_max_id(old_max_id) is None
    assert await residents.list_for_user(own.user_id) == []
    assert await OrgsRepo(session).list_for_user(own.user_id) == []
    kept = await RequestsRepo(session).get(request.id)
    assert kept is not None
    assert kept.author_user_id == own.user_id
    deleted = await events_of(session, EventType.ACCOUNT_DELETED)
    assert [event.user_id for event in deleted] == [own.user_id]
    recipients = await NotificationsRepo(session).recipients(
        [own.user_id],
        NotificationCategory.REQUESTS,
    )
    sender = MaxSender(cast(Bot, None), cast(BgManagerFactory, None))
    assert [
        await sender.send_message("✅ Заявка выполнена", user_id=recipient.max_user_id)
        for recipient in recipients
    ] == [None]


async def test_an_org_creator_keeps_the_data(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.CREATOR)

    with pytest.raises(NotEnoughRights, match=CREATOR_CANNOT_FORGET):
        await _profile_service(session).forget(own.user_id)

    user = await UsersRepo(session).get_by_id(own.user_id)
    assert user is not None
    assert user.name != FORGOTTEN_NAME


async def test_a_deleted_account_comes_back_as_a_new_one_asking_for_consent(
    bot_database_url: str,  # noqa: ARG001
) -> None:
    app = _app(CHECKER_TOKEN, make_bot_config().db)
    max_user = json.dumps({"id": secrets.randbits(40), "first_name": "Жека"})
    resident = {"WebAppData": signed_init_data(datetime.now(UTC), user=max_user)}
    checker = {"Authorization": f"Bearer {CHECKER_TOKEN}"}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        consented = await client.post(
            "/api/me/consent",
            headers=resident,
            json={"version": CONSENT_VERSION},
        )
        deleted = await client.delete("/api/me", headers=resident)
        back = await client.get("/api/me", headers=resident)
        refused = await client.delete("/api/me", headers=checker)

    assert deleted.status_code == 204
    assert back.json()["user_id"] != consented.json()["user_id"]
    assert back.json()["consent_version"] is None
    assert refused.status_code == 403
    assert refused.json()["error"]["detail"] == CHECKER_CANNOT_FORGET


def _file(directory: Path, age: timedelta, name: str = "") -> str:
    name = name or photo_name()
    path = directory / name
    path.write_bytes(b"x")
    stamp = (datetime.now(UTC) - age).timestamp()
    os.utime(path, (stamp, stamp))
    return name


async def test_the_purge_drops_old_photos_and_then_their_orphaned_files(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    tmp_path: Path,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    old = ATTACHMENT_TTL + timedelta(days=30)
    _file(tmp_path, timedelta(days=2))
    fresh = _file(tmp_path, timedelta(hours=1))
    open_photo = _file(tmp_path, old)
    closed_photo = _file(tmp_path, old)
    reading_photo = _file(tmp_path, old)
    requests = RequestsRepo(session)
    opened = await _complain(session, own.user_id, own.house_id)
    await requests.add_attachment(
        opened.id,
        open_photo,
        RequestAttachmentKind.ISSUE,
        own.user_id,
    )
    closed = await _complain(session, own.user_id, own.house_id)
    await requests.add_attachment(
        closed.id,
        closed_photo,
        RequestAttachmentKind.ISSUE,
        own.user_id,
    )
    stmt = (
        update(requests_table)
        .where(requests_table.c.id == closed.id)
        .values(done_at=datetime.now(UTC) - old)
    )
    await session.execute(stmt)
    reading = await MetersRepo(session).add_reading(
        await add_meter(session, own.flat_id),
        date(2020, 1, 1),
        {TariffZone.SINGLE: 1},
        [reading_photo],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC) - old,
        submitted_by=own.user_id,
    )
    service = RetentionService(
        FilesRepo(session),
        FilesService(FilesConfig(dir=str(tmp_path), max_size_mb=1), "test-token"),
        IdempotencyRepo(session),
    )

    first = await service.purge(datetime.now(UTC))
    await session.refresh(reading)
    second = await service.purge(datetime.now(UTC))

    assert first == 1
    assert second == 2
    assert reading.photo_paths == []
    assert await requests.list_attachments(closed.id) == []
    left = {path.name for path in tmp_path.iterdir()}  # noqa: ASYNC240
    assert left == {fresh, open_photo}


async def test_the_purge_keeps_documents_recent_readings_and_foreign_files(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    tmp_path: Path,
) -> None:
    own = await make_org_house_flat_user()
    old = ATTACHMENT_TTL + timedelta(days=30)
    house_document = _file(tmp_path, old)
    tariff_document = _file(tmp_path, old)
    reading_photo = _file(tmp_path, old)
    foreign = _file(tmp_path, old, "notes.txt")
    stmt = (
        update(houses_table)
        .where(houses_table.c.id == own.house_id)
        .values(documents=[house_document])
    )
    await session.execute(stmt)
    tariff = await add_tariff(session, own.house_id, 100_000)
    tariff.document_url = tariff_document
    reading = await MetersRepo(session).add_reading(
        await add_meter(session, own.flat_id),
        date(2020, 1, 1),
        {TariffZone.SINGLE: 1},
        [reading_photo],
        ocr_used=False,
        ocr_accepted=False,
        is_below_previous=False,
        submitted_at=datetime.now(UTC) - ATTACHMENT_TTL + timedelta(days=1),
        submitted_by=own.user_id,
    )
    service = RetentionService(
        FilesRepo(session),
        FilesService(FilesConfig(dir=str(tmp_path), max_size_mb=1), "test-token"),
        IdempotencyRepo(session),
    )

    first = await service.purge(datetime.now(UTC))
    await session.refresh(reading)
    second = await service.purge(datetime.now(UTC))

    assert (first, second) == (0, 0)
    assert reading.photo_paths == [reading_photo]
    left = {path.name for path in tmp_path.iterdir()}  # noqa: ASYNC240
    assert left == {house_document, tariff_document, reading_photo, foreign}


async def test_forget_cancels_upcoming_visits_and_clears_the_caller(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    request = await _complain(session, own.user_id, own.house_id)
    request.caller_name = "Мария Ивановна"
    request.caller_phone = "+70000000000"
    reception = ReceptionRepo(session)
    now = datetime.now(UTC)
    upcoming = await reception.create_appointment(
        own.org_id,
        own.house_id,
        own.user_id,
        now + timedelta(days=1),
        request.id,
    )
    past = await reception.create_appointment(
        own.org_id,
        own.house_id,
        own.user_id,
        now - timedelta(days=1),
        None,
    )

    await _profile_service(session).forget(own.user_id)

    assert upcoming.status is AppointmentStatus.CANCELLED
    assert past.status is AppointmentStatus.BOOKED
    cleared = await RequestsRepo(session).get(request.id)
    assert cleared is not None
    assert (cleared.caller_name, cleared.caller_phone) == (None, None)
