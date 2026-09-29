import io
import json
import secrets
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    Fixture,
    RecordingBroker,
    add_resident,
    add_user,
    empty_bot_setup,
    make_bot_config,
    make_config,
    signed_init_data,
)
from tests.test_announcements import (
    _add_resident,
    _bind_chat,
    _org_count,
    _service,
    _two_entrances,
)

from zheka.api.app import app_factory
from zheka.api.schemas.announcements import CreateAnnouncementRequest
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.config import FilesConfig
from zheka.core.deeplinks import ANNOUNCEMENTS_APP_PATH
from zheka.core.enums import AnnouncementChannel, OrgRole, RequestCategory
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import AnnouncementId, MaxUserId
from zheka.core.services.announcements import (
    DOCUMENT_NOT_FOUND,
    WORKS_ALREADY_OVER,
    WORKS_END_BEFORE_START,
    WorksDraft,
)
from zheka.core.services.demo import DEMO_LOCKED
from zheka.core.services.files import ONLY_PDF, FilesService
from zheka.core.texts import (
    ANNOUNCEMENT_HASHTAG,
    DOCUMENTS_IN_APP,
    OPEN_DOCUMENTS,
    planned_works,
    works_finished,
)
from zheka.infra.database.models import (
    Announcement,
    Flat,
    House,
    OrgMember,
    Organization,
    User,
)
from zheka.infra.database.repos.announcements import AnnouncementsRepo
from zheka.infra.database.repos.files import FilesRepo
from zheka.infra.database.repos.orgs import OrgsRepo

MOSCOW = ZoneInfo("Europe/Moscow")
TEXT = "Опрессовка системы водоснабжения\nВозможны перепады давления"
PDF = b"%PDF-1.4\n%modelled order\n"
WATER = RequestCategory.WATER_SUPPLY


class _Upload:
    def __init__(self, content_type: str, body: bytes) -> None:
        self.content_type = content_type
        self._body = io.BytesIO(body)

    async def read(self, size: int) -> bytes:
        return self._body.read(size)


def _files(directory: Path) -> FilesService:
    return FilesService(FilesConfig(dir=str(directory), max_size_mb=10), "token")


def _local_now() -> datetime:
    return datetime.now(MOSCOW).replace(tzinfo=None, second=0, microsecond=0)


def _tomorrow() -> date:
    return (datetime.now(MOSCOW) + timedelta(days=1)).date()


def _draft(
    starts_at: datetime,
    ends_at: datetime,
    category: RequestCategory | None = WATER,
) -> WorksDraft:
    return WorksDraft(category=category, starts_at=starts_at, ends_at=ends_at)


async def _pdf_name() -> str:
    files = FilesService(make_config().files, "test-token")
    return await files.save_document(_Upload("application/pdf", PDF))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("content_type", "body"),
    [("image/png", PDF), ("application/pdf", b"MZ\x90\x00not a pdf")],
    ids=["not-a-pdf-type", "fake-pdf"],
)
async def test_a_document_must_be_a_pdf_by_type_and_signature(
    tmp_path: Path,
    content_type: str,
    body: bytes,
) -> None:
    service = _files(tmp_path)

    with pytest.raises(InvalidRequest, match=ONLY_PDF):
        await service.save_document(_Upload(content_type, body))  # type: ignore[arg-type]

    assert list(tmp_path.iterdir()) == []  # noqa: ASYNC240


async def test_a_pdf_is_saved_under_a_pdf_name_and_signed(tmp_path: Path) -> None:
    service = _files(tmp_path)

    name = await service.save_document(_Upload("application/pdf", PDF))  # type: ignore[arg-type]

    assert name.endswith(".pdf")
    assert service.path_of(name).read_bytes() == PDF
    assert service.sign(name).startswith(f"/files/{name}?")


def test_the_works_period_names_the_end_day_only_when_it_differs() -> None:
    start = datetime(2026, 9, 29, 10, 0, tzinfo=MOSCOW)

    assert planned_works(WATER, start, start.replace(hour=18)) == (
        "🚧 Плановые работы: Водоснабжение, 29.09 10:00 - 18:00"
    )
    assert planned_works(None, start, datetime(2026, 10, 1, 18, 0, tzinfo=MOSCOW)) == (
        "🚧 Плановые работы, 29.09 10:00 - 01.10 18:00"
    )
    assert works_finished(None) == "✅ Плановые работы завершены"


async def test_planned_works_carry_their_period_and_documents_to_every_channel(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    await _bind_chat(session, data.house_id)
    await _add_resident(session, data.house_id)
    name = await _pdf_name()
    day = _tomorrow()

    created = await _service(session, publisher).create(
        data.org_id,
        data.user_id,
        [data.house_id],
        TEXT,
        [AnnouncementChannel.CHAT, AnnouncementChannel.DIRECT],
        works=_draft(datetime.combine(day, time(10)), datetime.combine(day, time(18))),
        documents=[{"name": name, "title": "Приказ № 12"}],
    )

    announcement = created.announcement
    assert announcement.works_category is WATER
    assert (announcement.works_from, announcement.works_until) == (
        datetime.combine(day, time(7), UTC),
        datetime.combine(day, time(15), UTC),
    )
    assert announcement.documents == [{"name": name, "title": "Приказ № 12"}]
    await publisher.flush()
    [direct] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    [chat] = broker.enqueued(TaskName.BROADCAST_TO_CHATS)
    heading, works, *_ = direct["text"].split("\n")
    assert heading.startswith("📢 Объявление от ")
    assert works == f"🚧 Плановые работы: Водоснабжение, {day:%d.%m} 10:00 - 18:00"
    assert direct["text"].endswith(f"давления\n\n{DOCUMENTS_IN_APP}")
    assert chat["text"] == f"{direct['text']}\n\n{ANNOUNCEMENT_HASHTAG}"
    assert {(sent["app_button"], sent["app_path"]) for sent in (direct, chat)} == {
        (OPEN_DOCUMENTS, ANNOUNCEMENTS_APP_PATH),
    }
    assert name in await FilesRepo(session).referenced_names()


@pytest.mark.parametrize(
    ("hours", "missing", "error", "message"),
    [
        ((18, 10), False, InvalidRequest, WORKS_END_BEFORE_START),
        ((-30, -26), False, InvalidRequest, WORKS_ALREADY_OVER),
        ((34, 42), True, EntityNotFound, DOCUMENT_NOT_FOUND),
    ],
    ids=["end-before-start", "over", "missing-document"],
)
async def test_wrong_works_or_a_missing_document_are_refused(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    hours: tuple[int, int],
    missing: bool,
    error: type[Exception],
    message: str,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    midnight = datetime.combine(_local_now().date(), time())
    starts, ends = (midnight + timedelta(hours=hour) for hour in hours)
    name = f"{uuid4().hex}.pdf" if missing else await _pdf_name()

    with pytest.raises(error, match=message):
        await _service(session).create(
            data.org_id,
            data.user_id,
            [data.house_id],
            TEXT,
            [AnnouncementChannel.DIRECT],
            works=_draft(starts, ends),
            documents=[{"name": name, "title": "Приказ"}],
        )

    assert await _org_count(session, data) == 0


async def test_active_works_match_the_category_the_time_and_the_scope(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    first, second = await _two_entrances(session, data)
    near = await _add_resident(session, data.house_id, flat_id=first)
    far = await _add_resident(session, data.house_id, flat_id=second)
    service = _service(session)
    now = _local_now()

    async def works(
        category: RequestCategory,
        starts_at: datetime,
        entrances: list[int] | None = None,
    ) -> Announcement:
        created = await service.create(
            data.org_id,
            data.user_id,
            [data.house_id],
            TEXT,
            [AnnouncementChannel.DIRECT],
            entrances=entrances,
            works=_draft(starts_at, starts_at + timedelta(hours=3), category),
        )
        return created.announcement

    water = await works(WATER, now - timedelta(hours=1))
    await works(RequestCategory.HEATING, now + timedelta(days=1))
    await works(RequestCategory.ELECTRICITY, now - timedelta(hours=1), [2])

    found = await service.active_works(near, data.house_id, WATER)
    assert found is not None
    assert found.announcement.id == water.id
    assert found.ends_at == water.works_until
    assert found.ends_at.utcoffset() == timedelta(hours=3)
    assert await service.active_works(near, data.house_id, RequestCategory.LEAK) is None
    assert (
        await service.active_works(near, data.house_id, RequestCategory.HEATING)
    ) is None
    assert (
        await service.active_works(near, data.house_id, RequestCategory.ELECTRICITY)
    ) is None
    assert (
        await service.active_works(far, data.house_id, RequestCategory.ELECTRICITY)
    ) is not None

    await service.finish_works(data.org_id, water.id, data.user_id)

    assert await service.active_works(near, data.house_id, WATER) is None


async def test_finishing_works_ends_them_and_tells_the_same_channels_quietly(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    chat_id = await _bind_chat(session, data.house_id)
    resident = await _add_resident(session, data.house_id)
    service = _service(session, publisher)
    now = _local_now()
    both = [AnnouncementChannel.CHAT, AnnouncementChannel.DIRECT]
    direct = [AnnouncementChannel.DIRECT]

    async def create(
        channels: list[AnnouncementChannel],
        works: WorksDraft | None,
    ) -> AnnouncementId:
        created = await service.create(
            data.org_id,
            data.user_id,
            [data.house_id],
            TEXT,
            channels,
            works=works,
        )
        return created.announcement.id

    going = _draft(now - timedelta(hours=1), now + timedelta(hours=2))
    ongoing = await create(both, going)
    quiet = await create(direct, going)
    upcoming = await create(
        direct,
        _draft(now + timedelta(days=1), now + timedelta(days=1, hours=2)),
    )
    plain = await create(direct, None)
    await publisher.flush()
    broker.messages.clear()
    before = datetime.now(UTC)

    finished = await service.finish_works(data.org_id, ongoing, data.user_id)

    until = finished.announcement.works_until
    assert until is not None
    assert before <= until <= datetime.now(UTC)
    session.expire_all()
    stored = await AnnouncementsRepo(session).get_for_org(ongoing, data.org_id)
    assert stored is not None
    assert stored.works_until == until
    await publisher.flush()
    [users] = broker.enqueued(TaskName.BROADCAST_TO_USERS)
    [chats] = broker.enqueued(TaskName.BROADCAST_TO_CHATS)
    assert users["user_ids"] == [resident]
    assert users["text"] == "✅ Работы завершены: Водоснабжение"
    assert users["silent"] is True
    assert users["announcement_id"] is None
    assert chats["chat_ids"] == [chat_id]
    assert (
        chats["text"] == f"✅ Работы завершены: Водоснабжение\n\n{ANNOUNCEMENT_HASHTAG}"
    )

    broker.messages.clear()
    await service.finish_works(data.org_id, quiet, data.user_id)
    await publisher.flush()
    assert broker.enqueued(TaskName.BROADCAST_TO_CHATS) == []
    for announcement_id in (ongoing, upcoming, plain):
        with pytest.raises(InvalidState):
            await service.finish_works(data.org_id, announcement_id, data.user_id)
    other = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    with pytest.raises(EntityNotFound):
        await service.finish_works(other.org_id, quiet, other.user_id)


async def test_the_app_uploads_a_pdf_announces_works_and_warns_the_request_form(
    bot_session: AsyncSession,
) -> None:
    org = Organization(
        name=f"УК {secrets.token_hex(4)}",
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Тестовая область, Тестоград, Тестовая, 1",
        registered_at=datetime.now(UTC),
        timezone="Europe/Moscow",
    )
    bot_session.add(org)
    await bot_session.flush()
    house = House(
        org_id=org.id,
        region="Тестовая область",
        city="Тестоград",
        street="Тестовая",
        building=secrets.token_hex(4),
        chat_binding_code=secrets.token_hex(4),
        timezone="Europe/Moscow",
    )
    bot_session.add(house)
    await bot_session.flush()
    flat = Flat(house_id=house.id, number="1")
    bot_session.add(flat)
    await bot_session.flush()
    house_id = house.id
    headers = {}
    for who in ("staff", "resident"):
        user = User(
            max_user_id=MaxUserId(secrets.randbits(40)),
            name="Сосед",
            consent_at=datetime.now(UTC),
        )
        bot_session.add(user)
        await bot_session.flush()
        if who == "staff":
            bot_session.add(
                OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.EMPLOYEE),
            )
        else:
            await add_resident(bot_session, user.id, house_id, flat.id)
        init_data = signed_init_data(
            datetime.now(UTC),
            user=json.dumps({"id": user.max_user_id, "first_name": "Сосед"}),
        )
        headers[who] = {"WebAppData": init_data}
    await bot_session.commit()
    app = app_factory(make_bot_config(), empty_bot_setup())
    pdf = {"file": ("order.pdf", PDF, "application/pdf")}
    now = _local_now()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        refused = [
            await client.post("/api/files", headers=headers["resident"], files=pdf),
            await client.post(
                "/api/admin/files",
                headers=headers["resident"],
                files=pdf,
            ),
            await client.post(
                "/api/admin/files",
                headers=headers["staff"],
                files={"file": ("order.pdf", b"MZ not a pdf", "application/pdf")},
            ),
        ]
        uploaded = await client.post(
            "/api/admin/files",
            headers=headers["staff"],
            files=pdf,
        )
        sent = await client.post(
            "/api/admin/announcements",
            headers=headers["staff"],
            json={
                "house_ids": [house_id],
                "text": TEXT,
                "channels": ["direct"],
                "works": {
                    "category": WATER.value,
                    "starts_at": f"{now - timedelta(hours=1):%Y-%m-%dT%H:%M}",
                    "ends_at": f"{now + timedelta(hours=2):%Y-%m-%dT%H:%M}",
                },
                "documents": [
                    {"name": uploaded.json()["name"], "title": "Приказ № 12"},
                ],
            },
        )
        [item] = (
            await client.get("/api/announcements", headers=headers["resident"])
        ).json()["items"]
        document = await client.get(item["documents"][0]["url"])
        similar = {"category": WATER.value}
        warned = await client.get(
            "/api/requests/similar",
            params=similar,
            headers=headers["resident"],
        )
        finish = f"/api/admin/announcements/{sent.json()['id']}/finish"
        finished = await client.post(finish, headers=headers["staff"])
        again = await client.post(finish, headers=headers["staff"])
        calm = await client.get(
            "/api/requests/similar",
            params=similar,
            headers=headers["resident"],
        )

    assert [response.status_code for response in refused] == [400, 403, 400]
    assert (uploaded.status_code, sent.status_code) == (200, 200)
    assert item["works"]["category"] == WATER.value
    assert item["documents"][0]["title"] == "Приказ № 12"
    assert document.status_code == 200
    assert document.content == PDF
    assert warned.json()["works"]["announcement_id"] == sent.json()["id"]
    assert warned.json()["works"]["title"] == "Опрессовка системы водоснабжения"
    assert (finished.status_code, again.status_code) == (200, 409)
    assert datetime.fromisoformat(
        finished.json()["works"]["ends_at"],
    ) < datetime.fromisoformat(item["works"]["ends_at"])
    assert calm.json()["works"] is None


@pytest.mark.parametrize(
    "documents",
    [[{"name": "a.pdf", "title": ""}], [{"name": "a.pdf", "title": "Приказ"}] * 6],
    ids=["untitled", "six"],
)
def test_documents_need_a_title_and_stop_at_five(
    documents: list[dict[str, str]],
) -> None:
    with pytest.raises(ValidationError):
        CreateAnnouncementRequest.model_validate(
            {"house_ids": [1], "text": TEXT, "documents": documents},
        )


async def test_a_photo_is_not_accepted_as_a_document(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    files = FilesService(make_config().files, "test-token")
    photo = await files.save(_Upload("image/png", b"\x89PNG\r\n\x1a\n"))  # type: ignore[arg-type]
    day = _tomorrow()

    with pytest.raises(EntityNotFound, match=DOCUMENT_NOT_FOUND):
        await _service(session).create(
            data.org_id,
            data.user_id,
            [data.house_id],
            TEXT,
            [AnnouncementChannel.DIRECT],
            works=_draft(
                datetime.combine(day, time(10)),
                datetime.combine(day, time(18)),
            ),
            documents=[{"name": photo, "title": "Приказ"}],
        )

    assert await _org_count(session, data) == 0


async def test_a_demo_org_finishes_only_its_own_works(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    data = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    org = await OrgsRepo(session).get(data.org_id)
    assert org is not None
    org.is_demo = True
    reviewer = await add_user(session, "Другой проверяющий")
    session.add(OrgMember(org_id=data.org_id, user_id=reviewer, role=OrgRole.ADMIN))
    await session.flush()
    service = _service(session)
    now = _local_now()
    created = await service.create(
        data.org_id,
        data.user_id,
        [data.house_id],
        TEXT,
        [AnnouncementChannel.DIRECT],
        works=_draft(now - timedelta(hours=1), now + timedelta(hours=2)),
    )
    works_id = created.announcement.id

    with pytest.raises(NotEnoughRights, match=DEMO_LOCKED):
        await service.finish_works(data.org_id, works_id, reviewer)
    finished = await service.finish_works(data.org_id, works_id, data.user_id)

    assert finished.announcement.works_until is not None
