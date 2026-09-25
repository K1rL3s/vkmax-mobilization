import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import FastAPI

from tests.conftest import empty_bot_setup, make_config

from zheka.api.app import app_factory

CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return app_factory(make_config(), empty_bot_setup())


@pytest.fixture(scope="module")
def openapi(app: FastAPI) -> dict[str, Any]:
    return app.openapi()


def test_openapi_is_served_under_api_prefix(app: FastAPI) -> None:
    assert app.openapi_url == "/api/openapi.json"


def test_every_route_has_russian_summary(openapi: dict[str, Any]) -> None:
    assert not [
        operation["operationId"]
        for methods in openapi["paths"].values()
        for operation in methods.values()
        if not CYRILLIC.search(operation.get("summary", ""))
    ]


def test_no_unreachable_validation_response(openapi: dict[str, Any]) -> None:
    assert not [
        operation["operationId"]
        for methods in openapi["paths"].values()
        for operation in methods.values()
        if "422" in operation["responses"]
    ]
    assert "HTTPValidationError" not in openapi["components"]["schemas"]


def test_committed_openapi_yaml_matches_the_app(openapi: dict[str, Any]) -> None:
    committed = Path(__file__).resolve().parents[2] / "openapi.yaml"

    assert yaml.safe_load(committed.read_text(encoding="utf-8")) == openapi, (
        "openapi.yaml устарел: запустите just openapi"
    )
