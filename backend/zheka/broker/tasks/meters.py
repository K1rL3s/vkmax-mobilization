from typing import Any

from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot
from maxo.dialogs import ShowMode
from taskiq import async_shared_broker

from zheka.bot.dialog_data import MeterPhotoData
from zheka.bot.states import MeterPhoto
from zheka.broker.task_names import TaskName
from zheka.broker.tasks.bot_requests import save_photos
from zheka.core.enums import TariffZone
from zheka.core.ids import UserId
from zheka.core.services.files import FilesService
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.max import MaxSender
from zheka.infra.yandex.vision import VisionClient


@async_shared_broker.task(task_name=TaskName.RECOGNIZE_METER_PHOTO.value)
@inject(patch_module=True)
async def recognize_meter_photo(
    user_id: UserId,
    data: dict[str, Any],
    bot: FromDishka[Bot],
    files_service: FromDishka[FilesService],
    vision: FromDishka[VisionClient],
    users_repo: FromDishka[UsersRepo],
    sender: FromDishka[MaxSender],
) -> int | None:
    user = await users_repo.get_by_id(user_id)
    if user is None:
        return None
    draft = MeterPhotoData.retort.load(data, MeterPhotoData)
    urls = [] if draft.photo_url is None else [draft.photo_url]
    names = await save_photos(bot, files_service, urls)
    draft.photo_name = names[0] if names else None
    values = (
        None if draft.photo_name is None else await vision.recognize(draft.photo_name)
    )
    draft.recognized = None if values is None else values.get(TariffZone.SINGLE)
    draft.value = draft.recognized
    await sender.start_dialog(
        MeterPhoto.confirm,
        user,
        notify=False,
        data=draft.to_data(),
        show_mode=ShowMode.SEND,
    )
    return draft.value
