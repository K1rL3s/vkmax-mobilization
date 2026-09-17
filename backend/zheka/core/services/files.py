import hashlib
import hmac
import re
import time
from datetime import timedelta
from pathlib import Path
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
ALLOWED_MIME = frozenset(_SUFFIX_BY_MIME)
FILE_URL_TTL = timedelta(hours=1)

# ровно то, что генерирует save: uuid4().hex плюс один из известных суффиксов -
# единственный способ отличить настоящее имя от подставленного пути
_SUFFIX_PATTERN = "|".join(re.escape(suffix) for suffix in _SUFFIX_BY_MIME.values())
_NAME_RE = re.compile(f"^[0-9a-f]{{32}}(?:{_SUFFIX_PATTERN})$")
_SIG_RE = re.compile("^[0-9a-f]{64}$")

# небольшой шаг, чтобы лимит размера ловился с точностью до куска, а не до мегабайта
_CHUNK_SIZE = 64 * 1024


class FilesService:
    __slots__ = ("_dir", "_max_bytes", "_max_size_mb", "_token")

    def __init__(self, config: FilesConfig, token: str) -> None:
        self._dir = Path(config.dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_size_mb = config.max_size_mb
        self._max_bytes = config.max_size_mb * 1024 * 1024
        self._token = token

    async def save(self, upload: UploadFile) -> str:
        content_type = (upload.content_type or "").split(";", 1)[0].strip()
        suffix = _SUFFIX_BY_MIME.get(content_type)
        if suffix is None:
            raise InvalidRequest("Поддерживаются только изображения")

        name = f"{uuid4().hex}{suffix}"
        destination = self.path_of(name)
        try:
            await self._write(destination, upload)
        except InvalidRequest:
            destination.unlink(missing_ok=True)
            raise
        return name

    async def _write(self, destination: Path, upload: UploadFile) -> None:
        written = 0
        with destination.open("wb") as out:
            while chunk := await upload.read(_CHUNK_SIZE):
                written += len(chunk)
                if written > self._max_bytes:
                    raise InvalidRequest(f"Файл больше {self._max_size_mb} МБ")
                out.write(chunk)

    def sign(self, name: str) -> str:
        self.path_of(name)
        exp = int(time.time() + FILE_URL_TTL.total_seconds())
        sig = self._sign(name, exp)
        return f"/files/{name}?exp={exp}&sig={sig}"

    def verify(self, name: str, exp: int, sig: str) -> None:
        self.path_of(name)
        expired = exp < int(time.time())
        # compare_digest на str падает TypeError на не-ASCII символах в sig,
        # а его тут никто не гарантировал - сперва форма, потом сравнение
        forged = not _SIG_RE.fullmatch(sig) or not hmac.compare_digest(
            sig.encode(),
            self._sign(name, exp).encode(),
        )
        if expired or forged:
            raise EntityNotFound("Файл не найден")

    def path_of(self, name: str) -> Path:
        # единственное место, где имя признается настоящим: sign, verify и
        # сам download_file проходят через него, а не проверяют форму порознь
        if not _NAME_RE.fullmatch(name):
            raise EntityNotFound("Файл не найден")
        return self._dir / name

    def _sign(self, name: str, exp: int) -> str:
        return hmac.new(
            self._token.encode(),
            f"{name}:{exp}".encode(),
            hashlib.sha256,
        ).hexdigest()
