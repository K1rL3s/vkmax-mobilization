from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import field
from typing import Any, ClassVar, Self

from adaptix import Retort
from maxo.dialogs import DialogManager

from zheka.base import ZhekaMutableType, ZhekaType
from zheka.core.enums import EventSource, RequestCategory
from zheka.core.ids import HouseId


class BaseDialogData(ZhekaMutableType, slots=True):
    # ZhekaMutableType, а не ZhekaType(frozen=False): mypy не наследует
    # frozen=False от базы и считает поля подклассов read-only. slots=True
    # роняет присваивание в поле с опечаткой прямо в рантайме
    retort: ClassVar[Retort] = Retort()

    @classmethod
    @contextmanager
    def proxy(cls, dialog_manager: DialogManager) -> Iterator[Self]:
        # без try/finally: упавшее тело не должно записать полумутацию
        dialog_data = cls.load(dialog_manager)
        yield dialog_data
        dialog_data.dump(dialog_manager)

    @classmethod
    def load(cls, dialog_manager: DialogManager) -> Self:
        return cls.retort.load(dialog_manager.dialog_data, cls)

    @classmethod
    def load_start(cls, dialog_manager: DialogManager) -> Self:
        # без data окно стартует с None, а битые данные должны упасть, а не
        # превратиться в значения по умолчанию
        start_data = dialog_manager.start_data
        return cls.retort.load({} if start_data is None else start_data, cls)

    def to_data(self) -> dict[str, Any]:
        data: dict[str, Any] = self.retort.dump(self, type(self))
        return data

    def dump(self, dialog_manager: DialogManager) -> None:
        # update, а не присваивание: чужие ключи в dialog_data переживают запись
        dialog_manager.dialog_data.update(self.to_data())


class ConsentData(BaseDialogData):
    # диплинк, который привел к согласию: после «Согласен» житель едет туда
    payload: str | None = None


class MenuData(BaseDialogData):
    notice: str | None = None


class HouseItem(ZhekaType):
    id: int
    title: str


class OnboardingData(BaseDialogData):
    city: str = ""
    houses: list[HouseItem] = field(default_factory=list)
    house_id: int | None = None
    entrance: int | None = None
    source: EventSource = EventSource.DIRECT

    def chosen_house(self) -> HouseId:
        # окно квартиры открывают только выбор дома и диплинк, и оба кладут дом
        if self.house_id is None:
            raise KeyError("house_id")
        return HouseId(self.house_id)


class NewRequestData(BaseDialogData):
    house_id: int | None = None
    flat_id: int | None = None
    category: RequestCategory | None = None
    description: str = ""
    photos: list[str] = field(default_factory=list)
    # номер заявки приносит задача, когда заявка создана
    request_id: int | None = None


class ExecutorCardData(BaseDialogData):
    # номер кладет задача, открывшая карточку; стек у карточки свой на заявку
    request_id: int


class ReviewData(BaseDialogData):
    request_id: int


class ChatBindingData(BaseDialogData):
    # чат и его название кладет задача: окно, которое она открывает, рисует
    # другая сессия, и строки chats, записанной этой задачей, оно не увидит
    chat_id: int
    title: str
    notice: str | None = None


class AccessSlotsData(BaseDialogData):
    # запрос кладет задача рассылки; стек у окна свой на запрос
    access_request_id: int
    notice: str | None = None
