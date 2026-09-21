import logging
from collections.abc import Sequence
from functools import partial

from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot
from taskiq import async_shared_broker

from zheka.bot.dialog_data import NewRequestData
from zheka.bot.states import NewRequest
from zheka.broker.task_names import TaskName
from zheka.core.enums import RequestCategory, RequestChannel
from zheka.core.errors import InvalidRequest
from zheka.core.ids import FlatId, HouseId, UserId
from zheka.core.services.files import FilesService
from zheka.core.services.requests import RequestDraft, RequestsService
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.max import MaxSender

logger = logging.getLogger(__name__)

# MAX отдает вложения-изображения по ссылке и без mime: тип уже проверил
# MessageInput, а FilesService из него выводит суффикс и потолок размера
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
) -> int:
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

    request_id = card.request.id
    user = await users_repo.get_by_id(user_id)
    if user is not None:
        # тот же стек, что у окна «Принял, оформляю»: житель видит, как оно
        # превращается в номер заявки, а не получает второе окно
        await sender.start_dialog(
            NewRequest.sent,
            user,
            data=NewRequestData(request_id=request_id).to_data(),
            stack_id=stack_id,
            notify=False,
        )
    return request_id


async def save_photos(
    bot: Bot, files_service: FilesService, photo_urls: Sequence[str]
) -> list[str]:
    photos = []
    for url in photo_urls:
        try:
            photos.append(
                await files_service.save_download(
                    PHOTO_MIME, partial(bot.download, url, seek=False)
                )
            )
        except InvalidRequest as error:
            logger.warning("Фото из бота не сохранено: %s", error)
    return photos
