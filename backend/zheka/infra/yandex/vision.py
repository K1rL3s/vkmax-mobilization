import base64
import logging
import re
from collections.abc import Mapping
from typing import Any

import httpx

from zheka.config import YandexConfig
from zheka.core.enums import TariffZone
from zheka.core.errors import EntityNotFound
from zheka.core.services.files import FilesService

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 3.0
_RECOGNIZE_URL = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText"
_MODEL = "meter"
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def parse_reading(text: str) -> int | None:
    match = _NUMBER_RE.search(text)
    if match is None:
        return None
    whole, _, frac = match.group().replace(",", ".").partition(".")
    try:
        return int(whole) * 1000 + int((frac + "000")[:3])
    except ValueError:
        return None


def _full_text(data: Mapping[str, Any]) -> str | None:
    try:
        text = data["result"]["textAnnotation"]["fullText"]
    except (KeyError, TypeError):
        return None
    return text if isinstance(text, str) else None


class VisionClient:
    __slots__ = ("_config", "_files")

    def __init__(self, config: YandexConfig, files_service: FilesService) -> None:
        self._config = config
        self._files = files_service

    async def recognize(self, photo_path: str) -> dict[TariffZone, int] | None:
        if not self._config.api_key or not self._config.folder_id:
            return None

        try:
            content = self._files.path_of(photo_path).read_bytes()
        except (EntityNotFound, OSError):
            return None

        data = await self._call(content)
        text = None if data is None else _full_text(data)
        value = None if text is None else parse_reading(text)
        if value is None:
            return None
        return {TariffZone.SINGLE: value}

    async def _call(self, content: bytes) -> dict[str, Any] | None:
        headers = {
            "Authorization": f"Api-Key {self._config.api_key}",
            "x-folder-id": self._config.folder_id or "",
        }
        payload = {
            "mimeType": "JPEG",
            "languageCodes": ["ru"],
            "model": _MODEL,
            "content": base64.b64encode(content).decode(),
        }
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    _RECOGNIZE_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("Не удалось распознать показание счетчика через OCR")
            return None
        return data
