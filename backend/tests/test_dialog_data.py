from types import SimpleNamespace
from typing import Any

import pytest

from zheka.bot.dialog_data import OnboardingData


def _manager() -> Any:
    return SimpleNamespace(dialog_data={})


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


def test_chosen_house_without_house_raises() -> None:
    with pytest.raises(KeyError):
        OnboardingData().chosen_house()
