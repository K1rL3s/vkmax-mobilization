from typing import Any, cast

import pytest
from maxo.dialogs import DialogManager

from zheka.bot.dialog_data import MenuData, OnboardingData


class _StubManager:
    def __init__(self, start_data: Any = None) -> None:
        self.dialog_data: dict[str, Any] = {}
        self.start_data = start_data


def _manager(start_data: Any = None) -> tuple[_StubManager, DialogManager]:
    stub = _StubManager(start_data)
    return stub, cast("DialogManager", stub)


def test_dump_keeps_foreign_keys() -> None:
    stub, manager = _manager()
    stub.dialog_data["foreign"] = 1

    OnboardingData(city="Казань").dump(manager)

    assert stub.dialog_data["foreign"] == 1
    assert stub.dialog_data["city"] == "Казань"


def test_proxy_drops_mutation_when_body_raises() -> None:
    stub, manager = _manager()

    def fail_midway() -> None:
        with OnboardingData.proxy(manager) as data:
            data.city = "Казань"
            raise RuntimeError

    with pytest.raises(RuntimeError):
        fail_midway()

    assert stub.dialog_data == {}


def test_load_start_without_data_gives_defaults() -> None:
    _, manager = _manager(None)

    assert MenuData.load_start(manager) == MenuData()


def test_chosen_house_without_house_raises() -> None:
    with pytest.raises(KeyError):
        OnboardingData().chosen_house()
