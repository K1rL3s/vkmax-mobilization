import hashlib
import hmac
import json
import urllib.parse
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from tests.conftest import empty_bot_setup, make_config

from zheka.api.app import app_factory
from zheka.api.dependencies.current_user import INIT_DATA_TTL, parse_init_data

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
