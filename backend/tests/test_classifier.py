import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from yarl import URL

from zheka.config import YandexConfig
from zheka.core.enums import RequestCategory
from zheka.infra.yandex import classifier as classifier_module
from zheka.infra.yandex.classifier import COMPLETION_URL, YandexClassifier

KEY = "b22-secret-api-key"
FOLDER = "b1gfolder"
TEXT = "Течет труба в ванной"

Reply = Callable[[], Awaitable[web.StreamResponse]]
Serve = Callable[..., Awaitable[tuple[YandexClassifier, list[web.Request]]]]


def _json(body: object, status: int = 200) -> Reply:
    async def reply() -> web.StreamResponse:
        return web.json_response(body, status=status)

    return reply


def _answer(text: str, *, wrapped: bool = True, status: int = 200) -> Reply:
    body = {
        "alternatives": [
            {
                "message": {"role": "assistant", "text": text},
                "status": "ALTERNATIVE_STATUS_FINAL",
            },
        ],
        "usage": {"inputTextTokens": "1", "completionTokens": "1"},
        "modelVersion": "07.03.2024",
    }
    return _json({"result": body} if wrapped else body, status)


def _status(code: int) -> Reply:
    return _json({"error": "nope"}, code)


async def _timeout() -> web.StreamResponse:
    await asyncio.sleep(1)
    return await _answer("leak")()


async def _html() -> web.StreamResponse:
    return web.Response(text="<html>Bad Gateway</html>", content_type="text/html")


@pytest.fixture
async def serve(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Serve]:
    monkeypatch.setattr(classifier_module, "LLM_TIMEOUT", 0.2)
    path = URL(COMPLETION_URL).path
    async with AsyncExitStack() as stack:
        http = await stack.enter_async_context(aiohttp.ClientSession())

        async def serve(
            reply: Reply,
            api_key: str | None = KEY,
            folder_id: str | None = FOLDER,
        ) -> tuple[YandexClassifier, list[web.Request]]:
            sent: list[web.Request] = []

            async def handle(request: web.Request) -> web.StreamResponse:
                await request.read()
                sent.append(request)
                return await reply()

            app = web.Application()
            app.router.add_post(path, handle)
            server = await stack.enter_async_context(TestServer(app))
            url = str(server.make_url(path))
            monkeypatch.setattr(classifier_module, "COMPLETION_URL", url)
            config = YandexConfig(api_key=api_key, folder_id=folder_id)
            return YandexClassifier(config, http), sent

        yield serve


@pytest.mark.parametrize(("api_key", "folder_id"), [(None, FOLDER), (KEY, None)])
async def test_without_credentials_no_request_is_made(
    serve: Serve,
    api_key: str | None,
    folder_id: str | None,
) -> None:
    classifier, sent = await serve(_answer("leak"), api_key, folder_id)

    assert await classifier.classify(TEXT) is None
    assert sent == []


async def test_a_valid_answer_is_the_category_after_trimming(serve: Serve) -> None:
    classifier, sent = await serve(_answer("  elevator\n"))

    assert await classifier.classify(TEXT) is RequestCategory.ELEVATOR
    [request] = sent
    assert request.headers["Authorization"] == f"Api-Key {KEY}"
    body = await request.json()
    assert body["modelUri"] == f"gpt://{FOLDER}/yandexgpt-5-lite"
    assert body["completionOptions"]["temperature"] == 0
    assert body["messages"][-1] == {"role": "user", "text": TEXT}


@pytest.mark.parametrize("answer", ["Протечка", "LEAK"])
async def test_an_answer_outside_the_enum_is_no_answer(
    serve: Serve,
    answer: str,
) -> None:
    classifier, _ = await serve(_answer(answer))

    assert await classifier.classify(TEXT) is None


@pytest.mark.parametrize("code", [401, 403])
async def test_a_refused_key_turns_the_classifier_off(serve: Serve, code: int) -> None:
    classifier, sent = await serve(_status(code))

    assert await classifier.classify(TEXT) is None
    assert await classifier.classify(TEXT) is None
    assert len(sent) == 1


@pytest.mark.parametrize("reply", [_status(429), _status(500), _timeout, _html])
async def test_a_failed_call_leaves_the_classifier_on(
    serve: Serve,
    reply: Reply,
) -> None:
    classifier, sent = await serve(reply)

    assert await classifier.classify(TEXT) is None
    assert await classifier.classify(TEXT) is None
    assert len(sent) == 2


async def test_an_error_status_is_logged_with_its_code(
    serve: Serve,
    caplog: pytest.LogCaptureFixture,
) -> None:
    classifier, _ = await serve(_answer("leak", status=503))

    with caplog.at_level(logging.WARNING, logger="zheka.infra.yandex.classifier"):
        assert await classifier.classify(TEXT) is None

    assert [record.args for record in caplog.records] == [(503,)]


@pytest.mark.parametrize(
    "reply",
    [_status(401), _status(500), _timeout, _answer("nonsense")],
)
async def test_the_key_never_reaches_a_log_record(
    serve: Serve,
    reply: Reply,
    caplog: pytest.LogCaptureFixture,
) -> None:
    classifier, _ = await serve(reply)

    with caplog.at_level(logging.DEBUG):
        await classifier.classify(TEXT)

    assert caplog.records
    for record in caplog.records:
        assert KEY not in record.getMessage()
        assert KEY not in (record.exc_text or "")


async def test_an_unwrapped_answer_is_read_too(serve: Serve) -> None:
    classifier, _ = await serve(_answer("heating", wrapped=False))

    assert await classifier.classify(TEXT) is RequestCategory.HEATING


@pytest.mark.parametrize("key", [f"{KEY}ё", f"{KEY}\n"])
async def test_a_key_that_cannot_be_a_header_turns_the_classifier_off(
    serve: Serve,
    caplog: pytest.LogCaptureFixture,
    key: str,
) -> None:
    classifier, sent = await serve(_answer("leak"), api_key=key)

    with caplog.at_level(logging.DEBUG):
        assert await classifier.classify(TEXT) is None
        assert await classifier.classify(TEXT) is None

    assert sent == []
    [record] = caplog.records
    assert record.levelno == logging.ERROR
    assert KEY not in record.getMessage()


async def test_the_model_gets_the_text_without_phone_and_flat(serve: Serve) -> None:
    classifier, sent = await serve(_answer("leak"))

    await classifier.classify("Течет стояк в кв. 45, звоните 8 917 123-45-67")

    [request] = sent
    body = await request.json()
    assert body["messages"][-1] == {
        "role": "user",
        "text": "Течет стояк в [КВАРТИРА], звоните [ТЕЛЕФОН]",
    }
