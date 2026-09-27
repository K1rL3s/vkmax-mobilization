import logging
from collections.abc import Sequence
from functools import partial
from html import escape

from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot
from taskiq import async_shared_broker

from zheka.bot.dialog_data import NewRequestData
from zheka.bot.handlers.requests.handlers import NOT_CREATED, NOT_CREATED_UNEXPECTED
from zheka.bot.states import NewRequest
from zheka.broker.task_names import TaskName
from zheka.core.enums import RequestCategory, RequestChannel
from zheka.core.errors import InvalidRequest, ZhekaError
from zheka.core.ids import FlatId, HouseId, UserId
from zheka.core.models import User
from zheka.core.services.files import FilesService
from zheka.core.services.requests import RequestDraft, RequestsService
from zheka.core.texts import MOMENT
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.max import MaxSender

logger = logging.getLogger(__name__)

PHOTO_MIME = "image/jpeg"


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
) -> int | None:
    user = await users_repo.get_by_id(user_id)
    try:
        photos = await save_photos(bot, files_service, photo_urls)
        card = await requests_service.create(
            user_id,
            house_id,
            RequestDraft(
                category=RequestCategory(category),
                description=description,
                flat_id=flat_id,
                photos=photos,
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
    deadline = card.house.local(card.request.deadline_at)
    outcome = NewRequestData(request_id=request_id, deadline=f"{deadline:{MOMENT}}")
    await _show_outcome(sender, user, stack_id, outcome)
    return request_id


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
