import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import empty_bot_setup

from zheka.api.app import app_factory
from zheka.config import load_config


async def test_healthcheck_reports_the_commit_the_image_was_built_from(
    database_url: str,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BUILD_COMMIT", "4f2c9e1")
    app = app_factory(load_config(), empty_bot_setup())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/healthcheck")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "commit": "4f2c9e1"}
