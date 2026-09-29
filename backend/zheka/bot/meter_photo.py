from maxo.dialogs import DialogManager, StartMode

from zheka.bot.cards import back_to_menu
from zheka.bot.dialog_data import MeterPhotoData
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import MeterPhoto
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.deeplinks import METERS_APP_PATH
from zheka.core.services.meter_photo import MeterPhotoService
from zheka.core.texts import MY_METERS


async def start_meter_photo(
    photo_url: str,
    dialog_manager: DialogManager,
    service: MeterPhotoService,
    publisher: TaskPublisher,
) -> None:
    choice = await service.meters(dialog_user_id(dialog_manager))
    if choice.refusal is not None or choice.period is None:
        await back_to_menu(
            dialog_manager,
            choice.refusal or "",
            MY_METERS,
            METERS_APP_PATH,
        )
        return
    data = MeterPhotoData(period=choice.period.isoformat(), photo_url=photo_url)
    if len(choice.cards) > 1:
        await dialog_manager.start(
            MeterPhoto.meter,
            data=data.to_data(),
            mode=StartMode.RESET_STACK,
        )
        return
    data.meter_id = choice.cards[0].meter.id
    await dialog_manager.start(
        MeterPhoto.wait,
        data=data.to_data(),
        mode=StartMode.RESET_STACK,
    )
    publish_recognition(publisher, dialog_manager, data)


def publish_recognition(
    publisher: TaskPublisher,
    dialog_manager: DialogManager,
    data: MeterPhotoData,
) -> None:
    publisher.publish(
        TaskName.RECOGNIZE_METER_PHOTO,
        user_id=dialog_user_id(dialog_manager),
        data=data.to_data(),
    )
