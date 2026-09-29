import json
import secrets
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    add_user,
    empty_bot_setup,
    make_bot_config,
    signed_init_data,
)

from zheka.api.app import app_factory
from zheka.base import ZhekaType
from zheka.config import FilesConfig
from zheka.core.consent import CONSENT_VERSION
from zheka.core.enums import OrgRole, RequestCategory
from zheka.core.ids import FlatId, HouseId, MaxUserId, UserId
from zheka.core.services.files import FilesService
from zheka.core.services.retention import KEY_TTL, RetentionService
from zheka.infra.database.models import (
    Flat,
    House,
    IdempotencyKey,
    OrgMember,
    Organization,
)
from zheka.infra.database.repos.files import FilesRepo
from zheka.infra.database.repos.idempotency import (
    ANOTHER_ROUTE,
    STILL_RUNNING,
    IdempotencyRepo,
)
from zheka.infra.database.tables.idempotency import idempotency_keys_table


class Cabinet(ZhekaType):
    client: AsyncClient
    headers: dict[str, str]
    user_id: UserId
    house_id: HouseId
    flat_id: FlatId


@pytest_asyncio.fixture
async def cabinet(
    bot_session: AsyncSession,
    bot_database_url: str,  # noqa: ARG001
) -> AsyncGenerator[Cabinet]:
    unique = secrets.token_hex(4)
    org = Organization(
        name=f"УК {unique}",
        inn=secrets.token_hex(6),
        phone="+70000000000",
        address="Тестовая область, Тестоград, Ключевая, 1",
        registered_at=datetime.now(UTC),
        timezone="Europe/Moscow",
    )
    bot_session.add(org)
    await bot_session.flush()
    house = House(
        org_id=org.id,
        region="Тестовая область",
        city="Тестоград",
        street="Ключевая",
        building=unique,
        cadastral_no=secrets.token_hex(8),
        chat_binding_code=secrets.token_hex(4),
        timezone="Europe/Moscow",
    )
    bot_session.add(house)
    await bot_session.flush()
    flat = Flat(house_id=house.id, number="1")
    bot_session.add(flat)
    await bot_session.flush()
    org_id, house_id, flat_id = org.id, house.id, flat.id
    await bot_session.commit()

    max_user_id = MaxUserId(secrets.randbits(40))
    headers = {
        "WebAppData": signed_init_data(
            datetime.now(UTC),
            user=json.dumps({"id": max_user_id, "first_name": "Жека"}),
        ),
    }
    app = app_factory(make_bot_config(), empty_bot_setup())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/me/consent",
            headers=headers,
            json={"version": CONSENT_VERSION},
        )
        me = await client.get("/api/me", headers=headers)
        user_id = UserId(me.json()["user_id"])
        bot_session.add(
            OrgMember(org_id=org_id, user_id=user_id, role=OrgRole.ADMIN),
        )
        await bot_session.commit()
        linked = await client.post(
            f"/api/houses/{house_id}/link",
            headers=headers,
            json={"flat_id": flat_id, "role": "owner"},
        )
        assert linked.status_code == 200, linked.text
        yield Cabinet(
            client=client,
            headers=headers,
            user_id=user_id,
            house_id=house_id,
            flat_id=flat_id,
        )


def _draft(**extra: object) -> dict[str, object]:
    return {
        "category": RequestCategory.LEAK.value,
        "description": "Течет стояк в санузле, вода уходит в подвал",
        **extra,
    }


async def _create(cabinet: Cabinet, key: UUID, **extra: object) -> Response:
    return await cabinet.client.post(
        "/api/requests",
        headers={**cabinet.headers, "Idempotency-Key": str(key)},
        json=_draft(**extra),
    )


async def test_the_same_key_creates_one_request_and_replays_its_card(
    cabinet: Cabinet,
) -> None:
    key = uuid4()

    first = await _create(cabinet, key)
    second = await _create(cabinet, key)
    mine = await cabinet.client.get("/api/requests", headers=cabinet.headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]
    assert mine.json()["total"] == 1


async def test_a_used_key_on_another_route_is_refused(cabinet: Cabinet) -> None:
    key = uuid4()

    await _create(cabinet, key)
    announced = await cabinet.client.post(
        "/api/admin/announcements",
        headers={**cabinet.headers, "Idempotency-Key": str(key)},
        json={"house_ids": [cabinet.house_id], "text": "Плановое отключение воды"},
    )

    assert announced.status_code == 400
    assert announced.json()["error"]["detail"] == ANOTHER_ROUTE


async def test_a_key_of_a_failed_action_is_free_again(cabinet: Cabinet) -> None:
    key = uuid4()

    failed = await _create(cabinet, key, flat_id=cabinet.flat_id + 10**6)
    retried = await _create(cabinet, key)
    mine = await cabinet.client.get("/api/requests", headers=cabinet.headers)

    assert failed.status_code == 404
    assert retried.status_code == 200, retried.text
    assert mine.json()["total"] == 1


async def test_a_key_without_a_saved_answer_is_refused(
    cabinet: Cabinet,
    bot_session: AsyncSession,
) -> None:
    await _create(cabinet, uuid4())
    stmt = select(idempotency_keys_table.c.route).where(
        idempotency_keys_table.c.user_id == cabinet.user_id,
    )
    route = await bot_session.scalar(stmt)
    assert route is not None
    unfinished = uuid4()
    bot_session.add(
        IdempotencyKey(user_id=cabinet.user_id, key=unfinished, route=route),
    )
    await bot_session.commit()

    refused = await _create(cabinet, unfinished)

    assert refused.status_code == 400
    assert refused.json()["error"]["detail"] == STILL_RUNNING


async def test_requests_without_a_key_are_both_created(cabinet: Cabinet) -> None:
    first = await cabinet.client.post(
        "/api/requests",
        headers=cabinet.headers,
        json=_draft(),
    )
    second = await cabinet.client.post(
        "/api/requests",
        headers=cabinet.headers,
        json=_draft(),
    )
    mine = await cabinet.client.get("/api/requests", headers=cabinet.headers)

    assert first.json()["id"] != second.json()["id"]
    assert mine.json()["total"] == 2


async def test_purge_drops_keys_older_than_a_day(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    repo = IdempotencyRepo(session)
    service = RetentionService(
        FilesRepo(session),
        FilesService(FilesConfig(dir=str(tmp_path), max_size_mb=1), "test-token"),
        repo,
    )
    fresh = uuid4()
    stale = uuid4()
    user_id = await add_user(session)
    for key, age in ((fresh, timedelta()), (stale, KEY_TTL + timedelta(minutes=1))):
        session.add(
            IdempotencyKey(
                user_id=user_id,
                key=key,
                route="/api/requests",
                response={"id": 1},
                created_at=datetime.now(UTC) - age,
            ),
        )
    await session.flush()

    removed = await service.purge_keys(datetime.now(UTC))

    assert removed == 1
    assert await repo.claim(user_id, stale, "/api/requests") is None
    assert await repo.claim(user_id, fresh, "/api/requests") == {"id": 1}


async def test_the_same_key_sends_one_answer_to_a_question_from_the_cabinet(
    cabinet: Cabinet,
) -> None:
    created = await _create(cabinet, uuid4())
    request_id = created.json()["id"]
    asked = await cabinet.client.post(
        f"/api/admin/requests/{request_id}/reply",
        headers=cabinet.headers,
        json={"text": "Под вами 45 или 47 квартира?", "question": True},
    )
    key = uuid4()
    answers = [
        await cabinet.client.post(
            f"/api/requests/{request_id}/messages",
            headers={**cabinet.headers, "Idempotency-Key": str(key)},
            json={"text": "47"},
        )
        for _ in range(2)
    ]
    card = await cabinet.client.get(
        f"/api/requests/{request_id}",
        headers=cabinet.headers,
    )

    assert asked.status_code == 200, asked.text
    assert asked.json()["question_asked_at"] is not None
    assert [answer.status_code for answer in answers] == [200, 200]
    assert answers[0].json() == answers[1].json()
    assert [message["text"] for message in card.json()["messages"]] == [
        "Под вами 45 или 47 квартира?",
        "47",
    ]
    assert card.json()["question_asked_at"] is None
    assert card.json()["resident_answered_at"] is not None
