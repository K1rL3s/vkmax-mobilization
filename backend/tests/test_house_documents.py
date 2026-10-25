from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    add_resident,
    add_user,
    empty_bot_setup,
    make_bot_config,
)
from tests.test_admin_map import _house, _org, _staff_headers
from tests.test_houses import _make_service as houses_service

from zheka.api.app import app_factory
from zheka.config import FilesConfig
from zheka.core.enums import OrgRole, ResidentStatus
from zheka.core.errors import EntityNotFound, InvalidRequest
from zheka.core.ids import HouseDocumentId
from zheka.core.services.announcements import DOCUMENT_NOT_FOUND
from zheka.core.services.files import FilesService
from zheka.core.services.house_documents import (
    EMPTY_TITLE,
    HOUSE_NOT_FOUND,
    HouseDocumentsService,
)
from zheka.infra.database.repos.houses import HousesRepo


def _service(session: AsyncSession, files_dir: Path) -> HouseDocumentsService:
    return HouseDocumentsService(
        HousesRepo(session),
        FilesService(FilesConfig(dir=str(files_dir), max_size_mb=1), "test-token"),
    )


def _pdf(files_dir: Path) -> str:
    name = f"{uuid4().hex}.pdf"
    (files_dir / name).write_bytes(b"%PDF-1.4\n")
    return name


async def test_only_residents_of_the_house_see_its_documents(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    tmp_path: Path,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id)
    stranger = await add_user(session)
    neighbour_elsewhere = await make_org_house_flat_user()
    await add_resident(
        session,
        neighbour_elsewhere.user_id,
        neighbour_elsewhere.house_id,
        neighbour_elsewhere.flat_id,
    )
    await _service(session, tmp_path).add(
        own.org_id,
        own.house_id,
        _pdf(tmp_path),
        "  Правила проживания ",
    )
    now = datetime.now(UTC)

    mine = await houses_service(session).house_card(own.house_id, own.user_id, now)
    outsiders = [
        await houses_service(session).house_card(own.house_id, user_id, now)
        for user_id in (stranger, neighbour_elsewhere.user_id)
    ]

    assert mine.documents is not None
    assert [document.title for document in mine.documents] == ["Правила проживания"]
    assert [card.documents for card in outsiders] == [None, None]


async def test_another_org_cannot_see_add_or_delete_house_documents(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    tmp_path: Path,
) -> None:
    own = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    service = _service(session, tmp_path)
    document = await service.add(own.org_id, own.house_id, _pdf(tmp_path), "Памятка")

    with pytest.raises(EntityNotFound, match=HOUSE_NOT_FOUND):
        await service.list(other.org_id, own.house_id)
    with pytest.raises(EntityNotFound, match=HOUSE_NOT_FOUND):
        await service.add(other.org_id, own.house_id, _pdf(tmp_path), "Памятка")
    with pytest.raises(EntityNotFound, match=HOUSE_NOT_FOUND):
        await service.delete(other.org_id, own.house_id, document.id)
    with pytest.raises(EntityNotFound, match=DOCUMENT_NOT_FOUND):
        await service.delete(other.org_id, other.house_id, document.id)

    assert await service.list(own.org_id, own.house_id) == [document]


async def test_a_house_document_is_an_uploaded_pdf_with_a_title(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    tmp_path: Path,
) -> None:
    own = await make_org_house_flat_user()
    service = _service(session, tmp_path)
    photo = f"{uuid4().hex}.png"
    (tmp_path / photo).write_bytes(b"\x89PNG\r\n\x1a\n")

    with pytest.raises(EntityNotFound, match=DOCUMENT_NOT_FOUND):
        await service.add(own.org_id, own.house_id, photo, "Фото")
    with pytest.raises(EntityNotFound, match=DOCUMENT_NOT_FOUND):
        await service.add(own.org_id, own.house_id, f"{uuid4().hex}.pdf", "Нет")
    with pytest.raises(InvalidRequest, match=EMPTY_TITLE):
        await service.add(own.org_id, own.house_id, _pdf(tmp_path), "   ")

    assert await service.list(own.org_id, own.house_id) == []


async def test_a_deleted_document_leaves_the_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    tmp_path: Path,
) -> None:
    own = await make_org_house_flat_user()
    service = _service(session, tmp_path)
    kept = await service.add(own.org_id, own.house_id, _pdf(tmp_path), "Памятка")
    gone = await service.add(own.org_id, own.house_id, _pdf(tmp_path), "Правила")

    await service.delete(own.org_id, own.house_id, gone.id)

    with pytest.raises(EntityNotFound, match=DOCUMENT_NOT_FOUND):
        await service.delete(own.org_id, own.house_id, gone.id)
    with pytest.raises(EntityNotFound, match=DOCUMENT_NOT_FOUND):
        await service.delete(own.org_id, own.house_id, HouseDocumentId(0))
    assert await service.list(own.org_id, own.house_id) == [kept]


async def test_an_unverified_resident_sees_the_documents_a_blocked_one_does_not(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    tmp_path: Path,
) -> None:
    own = await make_org_house_flat_user()
    await add_resident(session, own.user_id, own.house_id, own.flat_id, verified=False)
    blocked = await add_user(session)
    await add_resident(
        session,
        blocked,
        own.house_id,
        own.flat_id,
        status=ResidentStatus.BLOCKED,
        block_reason="Нарушение правил",
    )
    await _service(session, tmp_path).add(
        own.org_id,
        own.house_id,
        _pdf(tmp_path),
        "Памятка",
    )
    now = datetime.now(UTC)

    unverified = await houses_service(session).house_card(
        own.house_id,
        own.user_id,
        now,
    )
    refused = await houses_service(session).house_card(own.house_id, blocked, now)

    assert unverified.documents is not None
    assert [document.title for document in unverified.documents] == ["Памятка"]
    assert refused.documents is None


async def test_only_an_org_admin_manages_house_documents(
    bot_session: AsyncSession,
) -> None:
    org_id = await _org(bot_session)
    house_id = await _house(bot_session, org_id)
    headers = {
        role: await _staff_headers(bot_session, org_id, role)
        for role in (OrgRole.EMPLOYEE, OrgRole.ADMIN)
    }
    await bot_session.commit()
    url = f"/api/admin/houses/{house_id}/documents"
    body = {"name": f"{uuid4().hex}.pdf", "title": "Памятка"}

    seen = {}
    async with AsyncClient(
        transport=ASGITransport(app=app_factory(make_bot_config(), empty_bot_setup())),
        base_url="http://test",
    ) as client:
        for role, role_headers in headers.items():
            seen[role] = [
                (await client.get(url, headers=role_headers)).status_code,
                (await client.post(url, headers=role_headers, json=body)).status_code,
                (await client.delete(f"{url}/1", headers=role_headers)).status_code,
            ]

    assert seen == {OrgRole.EMPLOYEE: [403, 403, 403], OrgRole.ADMIN: [200, 404, 404]}
