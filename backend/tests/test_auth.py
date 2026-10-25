import hashlib
import hmac
import json
import urllib.parse
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from maxo.errors import InvalidWebAppInitDataError

from tests.conftest import (
    empty_bot_setup,
    make_bot_config,
    make_config,
    signed_init_data,
)

from zheka.api import app as app_module
from zheka.api.app import app_factory
from zheka.api.dependencies.current_user import (
    parse_init_data,
    signature_variant,
)
from zheka.config import ApiConfig, DbConfig
from zheka.core.consent import CONSENT_VERSION
from zheka.core.services.demo import (
    API_CHECKER_DEMO_NUMBER,
    CHECKER_ONLY,
    NOT_SEEDED,
)

TOKEN = make_config().max.token


def test_fresh_init_data_passes() -> None:
    init_data = parse_init_data(TOKEN, signed_init_data(datetime.now(UTC)))

    assert init_data.user.id == 42


def test_signed_init_data_with_a_line_break_is_refused() -> None:
    raw = signed_init_data(datetime.now(UTC), start_param="a\nb")

    with pytest.raises(InvalidWebAppInitDataError):
        parse_init_data(TOKEN, raw)


def test_week_old_init_data_passes() -> None:
    raw = signed_init_data(datetime.now(UTC) - timedelta(days=7))

    assert parse_init_data(TOKEN, raw).user.id == 42


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


async def test_the_checker_activates_only_its_demo_org(
    bot_database_url: str,  # noqa: ARG001
) -> None:
    app = _app(CHECKER_TOKEN, make_bot_config().db)
    checker = {"Authorization": f"Bearer {CHECKER_TOKEN}"}
    resident = {"WebAppData": signed_init_data(datetime.now(UTC))}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        for headers in (checker, resident):
            await client.post(
                "/api/me/consent",
                headers=headers,
                json={"version": CONSENT_VERSION},
            )
        own = await client.post(
            "/api/demo/activate",
            headers=checker,
            json={"number": API_CHECKER_DEMO_NUMBER},
        )
        refused = [
            await client.post("/api/demo/activate", headers=checker, json=body)
            for body in (
                None,
                {"number": 1},
                {"number": API_CHECKER_DEMO_NUMBER, "admin": True},
            )
        ]
        bare = await client.post("/api/demo/activate", headers=resident)
        unknown = await client.post(
            "/api/demo/activate",
            headers=checker,
            json={"number": 9},
        )

    assert own.json()["error"]["detail"] == NOT_SEEDED
    assert [response.status_code for response in refused] == [403, 403, 403]
    assert bare.json()["error"]["detail"] == NOT_SEEDED
    assert unknown.status_code == 400


async def test_the_checker_cannot_join_an_org_by_an_invite(
    bot_database_url: str,  # noqa: ARG001
) -> None:
    app = _app(CHECKER_TOKEN, make_bot_config().db)
    checker = {"Authorization": f"Bearer {CHECKER_TOKEN}"}
    resident = {"WebAppData": signed_init_data(datetime.now(UTC))}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        for headers in (checker, resident):
            await client.post(
                "/api/me/consent",
                headers=headers,
                json={"version": CONSENT_VERSION},
            )
        refused = await client.post("/api/org-invites/any/activate", headers=checker)
        unknown = await client.post("/api/org-invites/any/activate", headers=resident)

    assert refused.status_code == 403
    assert refused.json()["error"]["detail"] == CHECKER_ONLY
    assert unknown.status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/requests/99999999999999999999999",
        "/api/houses/99999999999999999999999",
        "/api/flats/99999999999999999999/meters",
        "/api/houses?q=Москва&offset=99999999999999999999",
    ],
)
async def test_an_id_beyond_bigint_is_a_bad_request(
    bot_database_url: str,  # noqa: ARG001
    path: str,
) -> None:
    app = _app(CHECKER_TOKEN, make_bot_config().db)
    headers = {"Authorization": f"Bearer {CHECKER_TOKEN}"}

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/me/consent",
            headers=headers,
            json={"version": CONSENT_VERSION},
        )
        response = await client.get(path, headers=headers)

    assert response.status_code == 400


async def test_the_wildcard_origin_carries_no_credentials() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_app(None)),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/openapi.json",
            headers={"Origin": "https://evil.example", "Cookie": "a=b"},
        )

    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers


async def test_rejected_init_data_is_logged_by_shape_only(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app_module, "setup_logger", lambda _: None)
    photo = "https://i.example/a+b&fn=Секрет"
    raw = signed_init_data(datetime.now(UTC), photo_url=photo).replace(
        "hash=",
        "hash=0",
    )

    async with AsyncClient(
        transport=ASGITransport(app=_app(None)),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/me",
            headers={"WebAppData": raw, "User-Agent": "MAX-mac"},
        )

    [message] = [
        record.getMessage()
        for record in caplog.records
        if record.name == "zheka.api.dependencies.current_user"
    ]
    assert response.status_code == 401
    assert "'hash'" in message
    assert "MAX-mac" in message
    assert all(
        value not in message
        for value in ("Жека", "Секрет", "i.example", raw.partition("hash=")[2])
    )


DESKTOP_FIELDS = {
    "auth_date": "1761400000",
    "chat": json.dumps({"id": 1, "type": "DIALOG"}),
    "ip": "203.0.113.7",
    "query_id": "q-1",
    "start_param": "",
    "user": json.dumps({"id": 42, "first_name": "Жека"}),
}
VARIANT_BASE = {"A": "A", "B": "B", "C": "C", "D": "A", "E": "B", "F": "C"}


def _signed_as(variant: str) -> str:
    raw = urllib.parse.urlencode(DESKTOP_FIELDS)
    bases = {
        "A": {key: value for key, value in DESKTOP_FIELDS.items() if value},
        "B": DESKTOP_FIELDS,
        "C": dict(part.split("=", 1) for part in raw.split("&")),
    }
    fields = bases[VARIANT_BASE[variant]]
    if variant in "DEF":
        fields = {key: value for key, value in fields.items() if key != "ip"}
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return f"{raw}&hash={signature}"


@pytest.mark.parametrize("variant", list(VARIANT_BASE))
def test_init_data_signed_by_any_known_variant_passes(variant: str) -> None:
    raw = _signed_as(variant)

    init_data = parse_init_data(TOKEN, raw)

    assert signature_variant(TOKEN, raw) == variant
    assert init_data.user.id == 42
    assert init_data.ip == (None if variant in "DEF" else "203.0.113.7")


@pytest.mark.parametrize("variant", list(VARIANT_BASE))
def test_a_tampered_user_fails_under_every_variant(variant: str) -> None:
    raw = _signed_as(variant).replace("%3A+42", "%3A+43")

    with pytest.raises(InvalidWebAppInitDataError):
        parse_init_data(TOKEN, raw)


def test_an_unsigned_ip_is_dropped() -> None:
    raw = _signed_as("D").replace("203.0.113.7", "198.51.100.66")

    init_data = parse_init_data(TOKEN, raw)

    assert init_data.user.id == 42
    assert init_data.ip is None
