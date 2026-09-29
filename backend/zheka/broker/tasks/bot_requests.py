import asyncio
import logging
from collections.abc import Sequence
from functools import partial
from html import escape
from typing import Any

from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot
from maxo.dialogs import ShowMode
from maxo.errors import MaxBotApiError, MaxBotNetworkError
from maxo.omit import is_defined
from taskiq import async_shared_broker

from zheka.bot.dialog_data import NewRequestData, transcript
from zheka.bot.handlers.requests.handlers import (
    NOT_CREATED,
    NOT_CREATED_UNEXPECTED,
)
from zheka.bot.states import NewRequest
from zheka.bot.voice import VOICE_FAILED
from zheka.broker.task_names import TaskName
from zheka.core.enums import RequestCategory, RequestChannel
from zheka.core.errors import InvalidRequest, ZhekaError
from zheka.core.ids import FlatId, HouseId, UserId
from zheka.core.models import User
from zheka.core.services.files import FilesService
from zheka.core.services.requests import RequestDraft, RequestsService
from zheka.core.texts import deadline_lines
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.max import MaxSender

logger = logging.getLogger(__name__)

PHOTO_MIME = "image/jpeg"
VOICE_RETRY_DELAYS = (1, 2, 4)


@async_shared_broker.task(task_name=TaskName.TRANSCRIBE_VOICE.value)
@inject(patch_module=True)
async def transcribe_voice(
    user_id: UserId,
    mid: str,
    draft: dict[str, Any],
    in_draft: bool,
    bot: FromDishka[Bot],
    users_repo: FromDishka[UsersRepo],
    sender: FromDishka[MaxSender],
) -> bool:
    user = await users_repo.get_by_id(user_id)
    if user is None:
        return False
    text = await _read_transcript(bot, mid)
    data = NewRequestData.retort.load(draft, NewRequestData)
    data.voice_pending = False
    if text:
        data.description = text
        state = NewRequest.attachments if in_draft else NewRequest.category
    elif in_draft:
        data.error = VOICE_FAILED
        state = NewRequest.description
    else:
        await sender.send_message(VOICE_FAILED, user_id=user.max_user_id)
        return False
    await sender.start_dialog(
        state,
        user,
        notify=False,
        data=data.to_data(),
        show_mode=ShowMode.SEND,
    )
    return bool(text)


async def _read_transcript(bot: Bot, mid: str) -> str:
    for delay in VOICE_RETRY_DELAYS:
        await asyncio.sleep(delay)
        try:
            message = await bot.get_message_by_id(message_id=mid)
        except (MaxBotApiError, MaxBotNetworkError):
            logger.warning("Голосовое %s не перечитано", mid)
            continue
        text = transcript(message.body)
        if text:
            return text
    logger.info("MAX не расшифровал голосовое %s", mid)
    return ""


@async_shared_broker.task(task_name=TaskName.CREATE_BOT_REQUEST.value)
@inject(patch_module=True)
async def create_bot_request(
    user_id: UserId,
    house_id: HouseId,
    flat_id: FlatId | None,
    category: str,
    description: str,
    photo_urls: Sequence[str],
    channel: str,
    stack_id: str,
    bot: FromDishka[Bot],
    files_service: FromDishka[FilesService],
    requests_service: FromDishka[RequestsService],
    users_repo: FromDishka[UsersRepo],
    sender: FromDishka[MaxSender],
    video_tokens: Sequence[str] = (),
) -> int | None:
    user = await users_repo.get_by_id(user_id)
    try:
        attachments = await save_photos(bot, files_service, photo_urls)
        attachments.extend(await save_videos(bot, files_service, video_tokens))
        card = await requests_service.create(
            user_id,
            house_id,
            RequestDraft(
                category=RequestCategory(category),
                description=description,
                flat_id=flat_id,
                attachments=attachments,
            ),
            RequestChannel(channel),
        )
    except ZhekaError as error:
        outcome = NewRequestData(error=NOT_CREATED.format(reason=escape(str(error))))
        await _show_outcome(sender, user, stack_id, outcome)
        return None
    except Exception:
        outcome = NewRequestData(error=NOT_CREATED_UNEXPECTED)
        await _show_outcome(sender, user, stack_id, outcome)
        raise

    request_id = card.request.id
    outcome = NewRequestData(
        request_id=request_id,
        deadline=deadline_lines(card.request, card.house),
    )
    await _show_outcome(sender, user, stack_id, outcome)
    return request_id


async def save_videos(
    bot: Bot,
    files_service: FilesService,
    video_tokens: Sequence[str],
) -> list[str]:
    videos = []
    for token in video_tokens:
        details = await bot.get_video_attachment_details(video_token=token)
        urls = details.urls
        url = None
        if is_defined(urls) and urls is not None:
            url = next(
                (
                    value
                    for value in (urls.mp4_480, urls.mp4_360, urls.mp4_720)
                    if is_defined(value) and value
                ),
                None,
            )
        if url is None:
            raise InvalidRequest("Видео пока недоступно, отправьте его ещё раз")
        videos.append(
            await files_service.save_download(
                "video/mp4",
                partial(bot.download, url, seek=False),
            ),
        )
    return videos


async def save_photos(
    bot: Bot,
    files_service: FilesService,
    photo_urls: Sequence[str],
) -> list[str]:
    photos = []
    for url in photo_urls:
        try:
            photos.append(
                await files_service.save_download(
                    PHOTO_MIME,
                    partial(bot.download, url, seek=False),
                ),
            )
        except InvalidRequest as error:
            logger.warning("Фото из бота не сохранено: %s", error)
    return photos


async def _show_outcome(
    sender: MaxSender,
    user: User | None,
    stack_id: str,
    outcome: NewRequestData,
) -> None:
    if user is None:
        return
    await sender.start_dialog(
        NewRequest.sent,
        user,
        data=outcome.to_data(),
        stack_id=stack_id,
        notify=False,
    )
