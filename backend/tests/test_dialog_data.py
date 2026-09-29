from types import SimpleNamespace
from typing import Any

import pytest
from maxo.types import MessageBody, PhotoAttachment, PhotoAttachmentPayload

from zheka.bot.dialog_data import OnboardingData, ReviewData
from zheka.core.services.requests import MAX_ATTACHMENTS


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


def test_a_rejection_keeps_no_more_photos_than_a_request_takes() -> None:
    photo = PhotoAttachment(
        payload=PhotoAttachmentPayload(
            photo_id=1,
            token="photo",  # noqa: S106
            url="https://max.ru/photo.jpg",
        ),
    )
    body = MessageBody(
        mid="photos",
        seq=1,
        text=None,
        attachments=[photo] * (MAX_ATTACHMENTS + 1),
    )
    data = ReviewData(request_id=1)

    data.attach_photos(body)

    assert len(data.photos) == MAX_ATTACHMENTS
