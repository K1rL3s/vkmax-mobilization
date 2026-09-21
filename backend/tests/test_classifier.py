import json
import logging
from collections.abc import Callable

import httpx
import pytest

from zheka.config import YandexConfig
from zheka.core.enums import RequestCategory
from zheka.infra.yandex.classifier import COMPLETION_URL, YandexClassifier

KEY = "b22-secret-api-key"
FOLDER = "b1gfolder"
TEXT = "Течет труба в ванной"

Handler = Callable[[httpx.Request], httpx.Response]


def _answer(text: str, *, wrapped: bool = True) -> httpx.Response:
    # REST-пример из concepts/generation/structured-output
    body = {
        "alternatives": [
            {
                "message": {"role": "assistant", "text": text},
                "status": "ALTERNATIVE_STATUS_FINAL",
            }
        ],
        "usage": {"inputTextTokens": "1", "completionTokens": "1"},
        "modelVersion": "07.03.2024",
    }
    return httpx.Response(200, json={"result": body} if wrapped else body)


def _classifier(
    handler: Handler, api_key: str | None = KEY, folder_id: str | None = FOLDER
) -> tuple[YandexClassifier, list[httpx.Request]]:
    sent: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return handler(request)

    classifier = YandexClassifier(
        YandexConfig(api_key=api_key, folder_id=folder_id), httpx.MockTransport(record)
    )
    return classifier, sent


def _status(code: int) -> Handler:
    return lambda _: httpx.Response(code, json={"error": "nope"})


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("timed out", request=request)


@pytest.mark.parametrize(("api_key", "folder_id"), [(None, FOLDER), (KEY, None)])
async def test_without_credentials_no_request_is_made(
    api_key: str | None, folder_id: str | None
) -> None:
    classifier, sent = _classifier(lambda _: _answer("leak"), api_key, folder_id)

    assert await classifier.classify(TEXT) is None
    assert sent == []


async def test_a_valid_answer_is_the_category_after_trimming() -> None:
    classifier, sent = _classifier(lambda _: _answer("  elevator\n"))

    assert await classifier.classify(TEXT) is RequestCategory.ELEVATOR
    [request] = sent
    assert str(request.url) == COMPLETION_URL
    assert request.headers["Authorization"] == f"Api-Key {KEY}"
    body = json.loads(request.content)
    assert body["modelUri"] == f"gpt://{FOLDER}/yandexgpt-5-lite"
    assert body["completionOptions"]["temperature"] == 0
    # текст жителя едет отдельным сообщением, а не вклеен в инструкцию
    assert body["messages"][-1] == {"role": "user", "text": TEXT}


@pytest.mark.parametrize("answer", ["Протечка", "LEAK"])
async def test_an_answer_outside_the_enum_is_no_answer(answer: str) -> None:
    classifier, _ = _classifier(lambda _: _answer(answer))

    assert await classifier.classify(TEXT) is None


@pytest.mark.parametrize("code", [401, 403])
async def test_a_refused_key_turns_the_classifier_off(code: int) -> None:
    classifier, sent = _classifier(_status(code))

    assert await classifier.classify(TEXT) is None
    assert await classifier.classify(TEXT) is None
    assert len(sent) == 1


@pytest.mark.parametrize("handler", [_status(500), _status(429), _timeout])
async def test_a_failed_call_leaves_the_classifier_on(handler: Handler) -> None:
    classifier, sent = _classifier(handler)

    assert await classifier.classify(TEXT) is None
    assert await classifier.classify(TEXT) is None
    assert len(sent) == 2


async def test_an_error_status_is_logged_with_its_code(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # тело ответа с ошибкой может оказаться похожим на ответ модели, и верить
    # ему нельзя: решает код
    empty, _ = _classifier(lambda _: httpx.Response(500, json={}))
    lookalike, _ = _classifier(
        lambda _: httpx.Response(503, content=_answer("leak").content)
    )

    with caplog.at_level(logging.WARNING, logger="zheka.infra.yandex.classifier"):
        assert await empty.classify(TEXT) is None
        assert await lookalike.classify(TEXT) is None

    assert [record.args for record in caplog.records] == [(500,), (503,)]


@pytest.mark.parametrize(
    "handler", [_status(401), _status(500), _timeout, lambda _: _answer("nonsense")]
)
async def test_the_key_never_reaches_a_log_record(
    handler: Handler, caplog: pytest.LogCaptureFixture
) -> None:
    classifier, _ = _classifier(handler)

    with caplog.at_level(logging.DEBUG):
        await classifier.classify(TEXT)

    assert caplog.records
    for record in caplog.records:
        assert KEY not in record.getMessage()
        assert KEY not in (record.exc_text or "")


async def test_an_unwrapped_answer_is_read_too() -> None:
    classifier, _ = _classifier(lambda _: _answer("heating", wrapped=False))

    assert await classifier.classify(TEXT) is RequestCategory.HEATING


async def test_a_key_that_cannot_be_a_header_turns_the_classifier_off(
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = f"{KEY}\u00a0"
    classifier, sent = _classifier(lambda _: _answer("leak"), api_key=key)

    with caplog.at_level(logging.DEBUG):
        assert await classifier.classify(TEXT) is None
        assert await classifier.classify(TEXT) is None

    assert sent == []
    [record] = caplog.records
    assert record.levelno == logging.ERROR
    assert KEY not in record.getMessage()
