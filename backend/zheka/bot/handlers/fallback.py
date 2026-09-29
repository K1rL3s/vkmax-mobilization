from dishka import FromDishka
from maxo import Router
from maxo.dialogs import DialogManager, StartMode
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import MessageInput
from maxo.types import MessageCreated

from zheka.bot.dialog_data import (
    MeterPhotoData,
    NewRequestData,
    has_voice,
    transcript,
)
from zheka.bot.meter_photo import start_meter_photo
from zheka.bot.middlewares.user import USER_KEY
from zheka.bot.states import Menu, NewRequest, entry_state
from zheka.bot.voice import VOICE_PENDING, publish_transcription
from zheka.broker.publisher import TaskPublisher
from zheka.core.danger import detect_danger
from zheka.core.models import User
from zheka.core.services.meter_photo import MeterPhotoService
from zheka.core.texts import danger_warning

router = Router(name=__name__)


@router.message_created()
async def no_state_handler(
    update: MessageCreated,
    dialog_manager: DialogManager,
    user: User,
    publisher: FromDishka[TaskPublisher],
    meter_photos: FromDishka[MeterPhotoService],
) -> None:
    body = update.message.body
    draft = NewRequestData.from_free_text(body)
    danger = detect_danger(body.text or transcript(body))
    if user.consent_at is None and danger is not None:
        await update.answer_text(danger_warning(danger.kind, None), notify=False)
    if user.consent_at is not None and draft is None and danger is not None:
        await dialog_manager.start(Menu.emergency, mode=StartMode.RESET_STACK)
        return
    photo_url = MeterPhotoData.photo_of(body)
    if user.consent_at is not None and draft is None and photo_url is not None:
        await start_meter_photo(photo_url, dialog_manager, meter_photos, publisher)
        return
    if user.consent_at is not None and draft is None and has_voice(body):
        await _transcribe(update, publisher, user)
        return
    if user.consent_at is None or draft is None:
        await dialog_manager.start(entry_state(user), mode=StartMode.RESET_STACK)
        return
    await dialog_manager.start(
        NewRequest.category,
        mode=StartMode.RESET_STACK,
        data=draft.to_data(),
    )


@inject
async def on_free_text(
    update: MessageCreated,
    _widget: MessageInput,
    dialog_manager: DialogManager,
    publisher: FromDishka[TaskPublisher],
) -> None:
    user: User = dialog_manager.middleware_data[USER_KEY]
    body = update.message.body
    draft = NewRequestData.from_free_text(body)
    danger = detect_danger(body.text or transcript(body))
    if user.consent_at is None:
        if danger is not None:
            await update.answer_text(danger_warning(danger.kind, None), notify=False)
        await dialog_manager.start(entry_state(user), mode=StartMode.RESET_STACK)
    elif draft is None and danger is not None:
        await dialog_manager.start(Menu.emergency, mode=StartMode.RESET_STACK)
    elif draft is None and has_voice(update.message.body):
        await _transcribe(update, publisher, user)
    elif draft is not None:
        await dialog_manager.start(
            NewRequest.category,
            mode=StartMode.RESET_STACK,
            data=draft.to_data(),
        )


async def _transcribe(
    update: MessageCreated,
    publisher: TaskPublisher,
    user: User,
) -> None:
    publish_transcription(
        publisher,
        user.id,
        update.message.body.mid,
        NewRequestData().to_data(),
        in_draft=False,
    )
    await update.answer_text(VOICE_PENDING, notify=False)
