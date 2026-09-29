import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import FileResponse
from httpx import ASGITransport, AsyncClient

from tests.conftest import photo_name

from zheka.api.dependencies.current_account import CurrentAccount
from zheka.api.routes.files import download_file, upload_file
from zheka.config import FilesConfig
from zheka.core.errors import EntityNotFound, InvalidRequest, TooManyRequests
from zheka.core.ids import UserId
from zheka.core.services.files import FilesService
from zheka.infra.quota import UPLOAD_CALLS, UploadQuota

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


async def test_uploads_past_the_hourly_quota_are_refused(tmp_path: Path) -> None:
    service = _make_service(tmp_path, max_size_mb=10)
    account = CurrentAccount(user_id=UserId(1), consent_at=None)
    quota = UploadQuota()
    for _ in range(UPLOAD_CALLS):
        await upload_file(account, _FakeUpload("image/png", 16), service, quota)  # type: ignore[arg-type]

    with pytest.raises(TooManyRequests):
        await upload_file(account, _FakeUpload("image/png", 16), service, quota)  # type: ignore[arg-type]
    assert len(list(tmp_path.iterdir())) == UPLOAD_CALLS  # noqa: ASYNC240


@pytest.mark.parametrize(
    ("mime", "suffix"),
    [("video/mp4", ".mp4"), ("video/quicktime", ".mov")],
)
async def test_video_has_its_own_limit_and_signed_type(
    tmp_path: Path,
    mime: str,
    suffix: str,
) -> None:
    service = _make_service(tmp_path, max_size_mb=1)
    upload = _FakeUpload(mime, 50 * 1024 * 1024)
    ref = await upload_file(
        CurrentAccount(user_id=UserId(1), consent_at=None),
        upload,  # type: ignore[arg-type]
        service,
        UploadQuota(),
    )
    assert ref.name.endswith(suffix)
    assert ref.is_video
    assert service.path_of(ref.name).stat().st_size == upload.size
    assert "sig=" in ref.url


async def test_oversized_video_is_removed(tmp_path: Path) -> None:
    service = _make_service(tmp_path, max_size_mb=10)
    with pytest.raises(InvalidRequest, match="Видео больше 50 МБ"):
        await service.save(_FakeUpload("video/mp4", 51 * 1024 * 1024))  # type: ignore[arg-type]
    assert not list(tmp_path.iterdir())  # noqa: ASYNC240


async def test_avi_is_rejected_before_download(tmp_path: Path) -> None:
    service = _make_service(tmp_path, max_size_mb=10)
    upload = _FakeUpload("video/x-msvideo", 100)
    with pytest.raises(InvalidRequest, match="MP4 или MOV"):
        await service.save(upload)  # type: ignore[arg-type]
    assert upload.total_read == 0


async def test_signed_video_supports_seeking(tmp_path: Path) -> None:

    files = _make_service(tmp_path, 10)
    name = await files.save(_FakeUpload("video/mp4", 1024))  # type: ignore[arg-type]
    app = FastAPI()

    @app.get("/files/{name}")
    async def download(name: str, exp: int, sig: str) -> FileResponse:
        return await download_file(name, exp, sig, files)

    async with AsyncClient(
        transport=ASGITransport(app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            files.sign(name),
            headers={"Range": "bytes=100-199"},
        )
    assert response.status_code == 206
    assert response.headers["content-range"] == "bytes 100-199/1024"
    assert response.headers["content-type"] == "video/mp4"
    assert response.content == b"x" * 100
