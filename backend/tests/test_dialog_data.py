from types import SimpleNamespace
from typing import Any

import pytest

from zheka.bot.dialog_data import ConsentData, OnboardingData


def _manager(start_data: Any = None) -> Any:
    return SimpleNamespace(dialog_data={}, start_data=start_data)


def test_dump_keeps_foreign_keys() -> None:
    manager = _manager()
    manager.dialog_data["foreign"] = 1

    OnboardingData(city="Казань").dump(manager)

    assert manager.dialog_data["foreign"] == 1
    assert manager.dialog_data["city"] == "Казань"


def test_proxy_drops_mutation_when_body_raises() -> None:
    manager = _manager()

    def fail_midway() -> None:
        with OnboardingData.proxy(manager) as data:
            data.city = "Казань"
            raise RuntimeError

    with pytest.raises(RuntimeError):
        fail_midway()

    assert manager.dialog_data == {}


def test_load_start_without_data_gives_defaults() -> None:
    assert ConsentData.load_start(_manager()) == ConsentData()


def test_chosen_house_without_house_raises() -> None:
    with pytest.raises(KeyError):
        OnboardingData().chosen_house()
