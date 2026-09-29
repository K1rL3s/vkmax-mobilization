from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import field
from typing import Any, ClassVar, Self

from adaptix import Retort
from maxo.dialogs import DialogManager
from maxo.omit import is_defined
from maxo.types import AudioAttachment, MessageBody, PhotoAttachment, VideoAttachment

from zheka.base import ZhekaMutableType, ZhekaType
from zheka.core.enums import EventSource, RequestCategory, RequestPlace
from zheka.core.ids import HouseId
from zheka.core.services.requests import MAX_ATTACHMENTS, MAX_VIDEOS, TOO_MANY_VIDEOS

MIN_REQUEST_TEXT = 15


def has_voice(body: MessageBody) -> bool:
    return any(isinstance(item, AudioAttachment) for item in body.attachments or [])


def transcript(body: MessageBody) -> str:
    for item in body.attachments or []:
        if isinstance(item, AudioAttachment) and is_defined(item.transcription):
            return (item.transcription or "").strip()
    return ""


class BaseDialogData(ZhekaMutableType, slots=True):
    retort: ClassVar[Retort] = Retort()

    @classmethod
    @contextmanager
    def proxy(cls, dialog_manager: DialogManager) -> Iterator[Self]:
        dialog_data = cls.load(dialog_manager)
        yield dialog_data
        dialog_data.dump(dialog_manager)

    @classmethod
    def load(cls, dialog_manager: DialogManager) -> Self:
        return cls.retort.load(dialog_manager.dialog_data, cls)

    @classmethod
    def load_start(cls, dialog_manager: DialogManager) -> Self:
        start_data = dialog_manager.start_data
        return cls.retort.load({} if start_data is None else start_data, cls)

    def to_data(self) -> dict[str, Any]:
        data: dict[str, Any] = self.retort.dump(self, type(self))
        return data

    def dump(self, dialog_manager: DialogManager) -> None:
        dialog_manager.dialog_data.update(self.to_data())


class ConsentData(BaseDialogData):
    payload: str | None = None
    given: bool = False


class HouseItem(ZhekaType):
    id: int
    title: str


class OnboardingData(BaseDialogData):
    city: str = ""
    street: str = ""
    query: str = ""
    missed: str | None = None
    by_geo: bool = False
    houses: list[HouseItem] = field(default_factory=list)
    house_id: int | None = None
    entrance: int | None = None
    source: EventSource = EventSource.DIRECT

    def chosen_house(self) -> HouseId:
        if self.house_id is None:
            raise KeyError("house_id")
        return HouseId(self.house_id)


class NewRequestData(BaseDialogData):
    house_id: int | None = None
    flat_id: int | None = None
    category: RequestCategory | None = None
    description: str = ""
    photos: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    request_id: int | None = None
    deadline: str | None = None
    error: str | None = None
    voice_pending: bool = False
    voice_failed: bool = False
    place: RequestPlace | None = None

    def attach_attachments(self, body: MessageBody) -> None:
        self.error = None
        for attach in body.attachments or []:
            if isinstance(attach, VideoAttachment) and len(self.videos) >= MAX_VIDEOS:
                self.error = f"🎬 {TOO_MANY_VIDEOS}"
                continue
            if len(self.photos) + len(self.videos) >= MAX_ATTACHMENTS:
                self.error = f"📷 Можно приложить не больше {MAX_ATTACHMENTS} файлов"
                break
            if isinstance(attach, PhotoAttachment):
                self.photos.append(attach.payload.url)
            elif isinstance(attach, VideoAttachment):
                self.videos.append(attach.payload.token)

    @classmethod
    def from_free_text(cls, body: MessageBody) -> Self | None:
        text = (body.text or "").strip()
        if len(text) < MIN_REQUEST_TEXT or text.startswith("/"):
            text = transcript(body)
        if not text:
            return None
        draft = cls(description=text)
        draft.attach_attachments(body)
        return draft


class MeterPhotoData(BaseDialogData):
    period: str | None = None
    meter_id: int | None = None
    photo_url: str | None = None
    photo_name: str | None = None
    value: int | None = None
    recognized: int | None = None
    anomaly_ack: bool = False
    notice: str | None = None
    manual: bool = False

    @staticmethod
    def photo_of(body: MessageBody) -> str | None:
        return next(
            (
                item.payload.url
                for item in body.attachments or []
                if isinstance(item, PhotoAttachment)
            ),
            None,
        )


class ExecutorCardData(BaseDialogData):
    request_id: int


class ReviewData(BaseDialogData):
    request_id: int
    comment: str = ""
    photos: list[str] = field(default_factory=list)

    def attach_photos(self, body: MessageBody) -> None:
        self.photos.extend(
            item.payload.url
            for item in body.attachments or []
            if isinstance(item, PhotoAttachment)
        )
        del self.photos[MAX_ATTACHMENTS:]


class ChatBindingData(BaseDialogData):
    chat_id: int
    title: str
    notice: str | None = None


class AccessSlotsData(BaseDialogData):
    access_request_id: int
    notice: str | None = None


class ChairmanData(BaseDialogData):
    code: str
    offer: str


def voice_url(body: MessageBody) -> str | None:
    for item in body.attachments or []:
        if isinstance(item, AudioAttachment):
            return item.payload.url
    return None


class QuestionData(BaseDialogData):
    request_id: int
