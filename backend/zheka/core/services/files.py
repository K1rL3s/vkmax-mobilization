import hashlib
import hmac
import re
import time
from collections.abc import Awaitable, Callable, Container
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO, cast
from uuid import uuid4

from fastapi import UploadFile

from zheka.config import FilesConfig
from zheka.core.errors import EntityNotFound, InvalidRequest

_SUFFIX_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
}
FILE_URL_TTL = timedelta(hours=1)

_SUFFIX_PATTERN = "|".join(re.escape(suffix) for suffix in _SUFFIX_BY_MIME.values())
_NAME_RE = re.compile(f"^[0-9a-f]{{32}}(?:{_SUFFIX_PATTERN})$")

_CHUNK_SIZE = 64 * 1024


class FilesService:
    __slots__ = ("_dir", "_max_size_mb", "_token")

    def __init__(self, config: FilesConfig, token: str) -> None:
        self._dir = Path(config.dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_size_mb = config.max_size_mb
        self._token = token

    async def save(self, upload: UploadFile) -> str:
        async def copy(out: BinaryIO) -> None:
            while chunk := await upload.read(_CHUNK_SIZE):
                out.write(chunk)

        content_type = (upload.content_type or "").split(";", 1)[0].strip()
        return await self.save_download(content_type, copy)

    def sign(self, name: str) -> str:
        self.path_of(name)
        exp = int(time.time() + FILE_URL_TTL.total_seconds())
        sig = self._sign(name, exp)
        return f"/files/{name}?exp={exp}&sig={sig}"

    def verify(self, name: str, exp: int, sig: str) -> None:
        self.path_of(name)
        expired = exp < int(time.time())
        forged = not hmac.compare_digest(sig.encode(), self._sign(name, exp).encode())
        if expired or forged:
            raise EntityNotFound("Файл не найден")

    def path_of(self, name: str) -> Path:
        if not _NAME_RE.fullmatch(name):
            raise EntityNotFound("Файл не найден")
        return self._dir / name

    def _sign(self, name: str, exp: int) -> str:
        return hmac.new(
            self._token.encode(),
            f"{name}:{exp}".encode(),
            hashlib.sha256,
        ).hexdigest()

    async def save_download(
        self,
        content_type: str,
        download: Callable[[BinaryIO], Awaitable[object]],
    ) -> str:
        suffix = _SUFFIX_BY_MIME.get(content_type)
        if suffix is None:
            raise InvalidRequest("Поддерживаются только изображения")

        name = f"{uuid4().hex}{suffix}"
        destination = self.path_of(name)
        try:
            with destination.open("wb") as out:
                writer = _CappedWriter(out, self._max_size_mb)
                await download(cast("BinaryIO", writer))
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        return name

    def remove_orphans(self, referenced: Container[str], before: datetime) -> int:
        removed = 0
        for path in self._dir.iterdir():
            if not _NAME_RE.fullmatch(path.name) or path.name in referenced:
                continue
            if path.stat().st_mtime >= before.timestamp():
                continue
            path.unlink(missing_ok=True)
            removed += 1
        return removed


class _CappedWriter:
    __slots__ = ("_max_size_mb", "_out", "_written")

    def __init__(self, out: BinaryIO, max_size_mb: int) -> None:
        self._out = out
        self._max_size_mb = max_size_mb
        self._written = 0

    def write(self, chunk: bytes) -> int:
        self._written += len(chunk)
        if self._written > self._max_size_mb * 1024 * 1024:
            raise InvalidRequest(f"Файл больше {self._max_size_mb} МБ")
        return self._out.write(chunk)

    def flush(self) -> None:
        self._out.flush()
