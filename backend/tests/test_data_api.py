import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = Path(__file__).with_name("data_api") / "DATA-API.schema.json"


@pytest.fixture(scope="module")
def data_api() -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "DATA-API.yaml").read_text(encoding="utf-8"),
    )
    return document


def test_data_api_yaml_matches_organizers_schema(data_api: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    assert not [
        f"{error.json_path}: {error.message}"
        for error in validator.iter_errors(data_api)
    ]


def test_data_api_checks_exist_in_openapi_yaml(data_api: dict[str, Any]) -> None:
    openapi = yaml.safe_load((REPO_ROOT / "openapi.yaml").read_text(encoding="utf-8"))

    assert not [
        check["id"]
        for check in data_api["checks"]
        if check["method"].lower() not in openapi["paths"].get(check["path"], {})
    ]
