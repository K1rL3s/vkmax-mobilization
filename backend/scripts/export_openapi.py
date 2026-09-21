"""Пишет схему OpenAPI в openapi.yaml в корне репозитория

Приложение только собирается и не запускается, поэтому ни база, ни Redis,
ни токен бота не нужны: недостающие переменные берутся из .env.example.

    uv run python scripts/export_openapi.py
"""

import os
from pathlib import Path

import yaml

from zheka.api.app import app_factory
from zheka.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]

os.environ["LOG_LEVEL"] = "WARNING"
app = app_factory(load_config(str(REPO_ROOT / ".env.example")))
(REPO_ROOT / "openapi.yaml").write_text(
    yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False, width=10**9),
    encoding="utf-8",
)
