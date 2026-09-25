import time
from pathlib import Path

import pytest

from tests.conftest import photo_name

from zheka.config import FilesConfig
from zheka.core.errors import EntityNotFound, InvalidRequest
from zheka.core.services.files import FilesService

_TOKEN = "test-max-token"  # noqa: S105


class _FakeUpload:
    def __init__(self, content_type: str, size: int) -> None:
        self.content_type = content_type
        self.size = size
        self._buffer = b"x" * size
        self.total_read = 0

    async def read(self, size: int) -> bytes:
        end = self.total_read + size
        chunk, self.total_read = self._buffer[self.total_read : end], end
        return chunk


def _make_service(tmp_path: Path, max_size_mb: int) -> FilesService:
    return FilesService(FilesConfig(dir=str(tmp_path), max_size_mb=max_size_mb), _TOKEN)


@pytest.mark.parametrize(
    ("content_type", "size"),
    [("image/png", 5 * 1024 * 1024), ("application/pdf", 1024)],
    ids=["oversized", "not-an-image"],
)
async def test_save_rejects_an_upload_before_reading_it_fully(
    tmp_path: Path,
    content_type: str,
    size: int,
) -> None:
    service = _make_service(tmp_path, max_size_mb=1)
    upload = _FakeUpload(content_type, size=size)

    with pytest.raises(InvalidRequest):
        await service.save(upload)  # type: ignore[arg-type]

    assert upload.total_read < upload.size
    assert list(tmp_path.iterdir()) == []  # noqa: ASYNC240


async def test_save_writes_the_file_under_its_generated_name(tmp_path: Path) -> None:
    service = _make_service(tmp_path, max_size_mb=10)
    upload = _FakeUpload("image/jpeg; charset=UTF-8", size=1024)

    name = await service.save(upload)  # type: ignore[arg-type]

    assert service.path_of(name).read_bytes() == b"x" * 1024
    assert name.endswith(".jpg")


def test_verify_accepts_a_freshly_signed_link(tmp_path: Path) -> None:
    service = _make_service(tmp_path, max_size_mb=10)

    url = service.sign(photo_name())
    name, query = url.removeprefix("/files/").split("?", 1)
    params = dict(pair.split("=") for pair in query.split("&"))

    service.verify(name, int(params["exp"]), params["sig"])


def test_verify_rejects_an_expired_link(tmp_path: Path) -> None:
    service = _make_service(tmp_path, max_size_mb=10)
    name = photo_name()
    expired = int(time.time()) - 1
    sig = service._sign(name, expired)  # noqa: SLF001

    with pytest.raises(EntityNotFound):
        service.verify(name, expired, sig)


@pytest.mark.parametrize("sig", ["forged", "é" * 64])
def test_verify_rejects_a_forged_signature(tmp_path: Path, sig: str) -> None:
    service = _make_service(tmp_path, max_size_mb=10)
    exp = int(time.time()) + 3600

    with pytest.raises(EntityNotFound):
        service.verify(photo_name(), exp, sig)


@pytest.mark.parametrize(
    "name",
    ["../../etc/passwd", "g" * 32 + ".jpg", "0" * 32 + ".php"],
)
def test_a_name_that_is_not_generated_is_neither_served_nor_signed(
    tmp_path: Path,
    name: str,
) -> None:
    service = _make_service(tmp_path, max_size_mb=10)
    exp = int(time.time()) + 3600

    with pytest.raises(EntityNotFound):
        service.path_of(name)
    with pytest.raises(EntityNotFound):
        service.sign(name)
    with pytest.raises(EntityNotFound):
        service.verify(name, exp, service._sign(name, exp))  # noqa: SLF001
