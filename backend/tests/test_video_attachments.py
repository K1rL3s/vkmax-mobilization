from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from unittest.mock import AsyncMock

import pytest
from maxo import Bot
from maxo.types import (
    MediaAttachmentPayload,
    MessageBody,
    VideoAttachment,
    VideoAttachmentDetails,
    VideoAttachmentRequest,
    VideoUrls,
)
from maxo.types.facades.attachments import AttachmentsFacade

from zheka.bot.dialog_data import NewRequestData
from zheka.broker.tasks.bot_requests import save_videos
from zheka.config import FilesConfig
from zheka.core.errors import InvalidRequest
from zheka.core.ids import MaxChatId, MaxUserId
from zheka.core.models import User
from zheka.core.services.files import FilesService
from zheka.infra.max import MaxSender


@pytest.mark.parametrize(
    ("urls", "expected"),
    [
        (VideoUrls(mp4_480="480", mp4_360="360", mp4_720="720"), "480"),
        (VideoUrls(mp4_360="360", mp4_720="720"), "360"),
        (VideoUrls(mp4_720="720"), "720"),
    ],
)
async def test_bot_downloads_the_best_available_mp4(
    tmp_path: Path,
    urls: VideoUrls,
    expected: str,
) -> None:
    bot = AsyncMock(spec=Bot)
    bot.get_video_attachment_details = AsyncMock()
    bot.download = AsyncMock()
    bot.get_video_attachment_details.return_value = VideoAttachmentDetails(
        token=str(1),
        duration=12,
        width=640,
        height=480,
        urls=urls,
    )

    async def download(url: str, out: BinaryIO, *, seek: bool) -> None:
        assert url == expected
        assert not seek
        out.write(b"\x00\x00\x00\x18ftypmp42")

    bot.download.side_effect = download
    files = FilesService(FilesConfig(dir=str(tmp_path), max_size_mb=10), "test")
    names = await save_videos(bot, files, [str(1)])
    bot.get_video_attachment_details.assert_awaited_once_with(video_token=str(1))
    assert names[0].endswith(".mp4")
    assert files.path_of(names[0]).read_bytes() == b"\x00\x00\x00\x18ftypmp42"


@pytest.mark.parametrize("urls", [None, VideoUrls()])
async def test_unavailable_video_does_not_silently_disappear(
    tmp_path: Path,
    urls: VideoUrls | None,
) -> None:
    bot = AsyncMock(spec=Bot)
    bot.get_video_attachment_details = AsyncMock()
    bot.download = AsyncMock()
    bot.get_video_attachment_details.return_value = VideoAttachmentDetails(
        token=str(1),
        duration=12,
        width=640,
        height=480,
        urls=urls,
    )
    files = FilesService(FilesConfig(dir=str(tmp_path), max_size_mb=10), "test")
    with pytest.raises(InvalidRequest, match="Видео пока недоступно"):
        await save_videos(bot, files, [str(1)])
    bot.download.assert_not_called()


def test_draft_keeps_two_video_tokens_and_reports_overflow() -> None:
    body = MessageBody(
        mid="video",
        seq=1,
        text="Течет вода с потолка",
        attachments=[
            VideoAttachment(
                payload=MediaAttachmentPayload(
                    token=str(n),
                    url="https://max.ru/video",
                ),
            )
            for n in range(3)
        ],
    )
    draft = NewRequestData.from_free_text(body)
    assert draft is not None
    assert draft.videos == ["0", "1"]
    assert draft.error == "🎬 Можно приложить не больше 2 видео"
    assert (
        NewRequestData.retort.load(draft.to_data(), NewRequestData).videos
        == draft.videos
    )


def test_draft_counts_videos_toward_total_attachments() -> None:
    draft = NewRequestData(photos=["photo"] * 11)
    body = MessageBody(
        mid="video",
        seq=1,
        text=None,
        attachments=[
            VideoAttachment(
                payload=MediaAttachmentPayload(
                    token=str(n),
                    url="https://max.ru/video",
                ),
            )
            for n in range(2)
        ],
    )
    draft.attach_attachments(body)
    assert draft.videos == ["0"]
    assert draft.error == "📷 Можно приложить не больше 12 файлов"


@pytest.mark.parametrize("unavailable", ["seeded", "no-chat", "stopped", None])
async def test_video_sender_uploads_only_for_a_live_recipient(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unavailable: str | None,
) -> None:
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock()
    upload = AsyncMock(return_value=[VideoAttachmentRequest.factory(token=str(1))])
    monkeypatch.setattr(AttachmentsFacade, "build_attachments", upload)
    sender = MaxSender(bot, AsyncMock())
    user = User(
        max_user_id=MaxUserId(-1 if unavailable == "seeded" else 123),
        name="Исполнитель",
        max_chat_id=None if unavailable == "no-chat" else MaxChatId(123),
        bot_stopped_at=datetime.now(UTC) if unavailable == "stopped" else None,
    )
    path = tmp_path / "video.mp4"
    await sender.send_video(path, user, 46)
    if unavailable:
        upload.assert_not_awaited()
        bot.send_message.assert_not_awaited()
    else:
        upload.assert_awaited_once()
        assert upload.call_args.kwargs["files"][0].path == path
        bot.send_message.assert_awaited_once_with(
            user_id=123,
            text="🎬 Видео к заявке №46",
            attachments=upload.return_value,
            notify=False,
        )
