import logging

import aiohttp

from zheka.config import YandexConfig

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10.0
_RECOGNIZE_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"


class SpeechClient:
    __slots__ = ("_config", "_session")

    def __init__(self, config: YandexConfig, session: aiohttp.ClientSession) -> None:
        self._config = config
        self._session = session

    async def recognize(self, audio: bytes) -> str:
        if not self.configured:
            return ""
        params = {
            "folderId": self._config.folder_id or "",
            "lang": "ru-RU",
            "format": "oggopus",
        }
        try:
            async with self._session.post(
                _RECOGNIZE_URL,
                params=params,
                headers={"Authorization": f"Api-Key {self._config.api_key}"},
                data=audio,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
            ) as response:
                if not response.ok:
                    logger.warning(
                        "SpeechKit ответил HTTP %s: %s",
                        response.status,
                        await response.text(),
                    )
                    return ""
                data: object = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            logger.warning("Не удалось распознать голосовое через SpeechKit")
            return ""
        result = data.get("result") if isinstance(data, dict) else None
        return result.strip() if isinstance(result, str) else ""

    @property
    def configured(self) -> bool:
        return bool(self._config.api_key and self._config.folder_id)
