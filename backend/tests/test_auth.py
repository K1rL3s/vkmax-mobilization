import hashlib
import hmac
import json
import urllib.parse
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from tests.conftest import empty_bot_setup, make_bot_config, make_config

from zheka.api.app import app_factory
from zheka.api.dependencies.current_user import INIT_DATA_TTL, parse_init_data
from zheka.config import ApiConfig, DbConfig
from zheka.core.consent import CONSENT_VERSION
from zheka.core.services.demo import NOT_SEEDED

TOKEN = make_config().max.token


def signed_init_data(auth_date: datetime) -> str:
    fields = {
        "auth_date": str(int(auth_date.timestamp())),
        "chat": json.dumps({"id": 1, "type": "DIALOG"}),
        "user": json.dumps({"id": 42, "first_name": "Жека"}),
    }
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(fields)


def test_fresh_init_data_passes() -> None:
    init_data = parse_init_data(TOKEN, signed_init_data(datetime.now(UTC)))

    assert init_data.user.id == 42


async def test_day_old_init_data_is_401() -> None:
    app = app_factory(make_config(), empty_bot_setup())
    stale = signed_init_data(datetime.now(UTC) - INIT_DATA_TTL - timedelta(minutes=1))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/me", headers={"WebAppData": stale})

    assert response.status_code == 401


CHECKER_TOKEN = "checker-token"  # noqa: S105


def _app(test_token: str | None, db: DbConfig | None = None) -> FastAPI:
    config = make_config()
    config = replace(
        config,
        api=ApiConfig(cors=(), test_token=test_token),
        db=db or config.db,
    )
    return app_factory(config, empty_bot_setup())


async def _get_me(app: FastAPI, headers: dict[str, str]) -> Response:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.get("/api/me", headers=headers)


@pytest.mark.parametrize(
    ("test_token", "headers"),
    [
        (CHECKER_TOKEN, {"Authorization": "Bearer wrong-token"}),
        (None, {"Authorization": f"Bearer {CHECKER_TOKEN}"}),
        (CHECKER_TOKEN, {}),
    ],
)
async def test_a_request_without_a_valid_credential_is_401(
    test_token: str | None,
    headers: dict[str, str],
) -> None:
    response = await _get_me(_app(test_token), headers)

    assert response.status_code == 401


async def test_the_test_token_acts_as_one_synthetic_checker(
    bot_database_url: str,  # noqa: ARG001
) -> None:
    app = _app(CHECKER_TOKEN, make_bot_config().db)
    headers = {"Authorization": f"Bearer {CHECKER_TOKEN}"}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        me = await client.get("/api/me", headers=headers)
        consents = [
            await client.post(
                "/api/me/consent",
                headers=headers,
                json={"version": CONSENT_VERSION},
            )
            for _ in range(2)
        ]
        again = await client.get("/api/me", headers=headers)

    assert me.status_code == 200
    assert me.json()["name"] == "Проверяющий API"
    assert [response.status_code for response in consents] == [200, 200]
    assert again.json()["user_id"] == me.json()["user_id"]
    assert again.json()["consent_version"] == CONSENT_VERSION


async def test_the_checker_activates_demo_with_or_without_a_body(
    bot_database_url: str,  # noqa: ARG001
) -> None:
    app = _app(CHECKER_TOKEN, make_bot_config().db)
    headers = {"Authorization": f"Bearer {CHECKER_TOKEN}"}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/me/consent",
            headers=headers,
            json={"version": CONSENT_VERSION},
        )
        bare = await client.post("/api/demo/activate", headers=headers)
        unknown = await client.post(
            "/api/demo/activate",
            headers=headers,
            json={"number": 9},
        )

    assert bare.json()["error"]["detail"] == NOT_SEEDED
    assert unknown.status_code == 400
