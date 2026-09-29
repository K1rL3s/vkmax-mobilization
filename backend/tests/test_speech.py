import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from zheka.config import YandexConfig
from zheka.infra.yandex.speech import SpeechClient

AUDIO = b"OggS-voice"
CONFIGURED = YandexConfig(api_key="key", folder_id="folder")


async def _recognize(
    monkeypatch: pytest.MonkeyPatch,
    config: YandexConfig,
    reply: web.StreamResponse,
) -> tuple[str, list[tuple[web.Request, bytes]]]:
    sent: list[tuple[web.Request, bytes]] = []

    async def handle(request: web.Request) -> web.StreamResponse:
        sent.append((request, await request.read()))
        return reply

    app = web.Application()
    app.router.add_post("/stt", handle)
    async with TestServer(app) as server, aiohttp.ClientSession() as http:
        url = str(server.make_url("/stt"))
        monkeypatch.setattr("zheka.infra.yandex.speech._RECOGNIZE_URL", url)
        text = await SpeechClient(config, http).recognize(AUDIO)
    return text, sent


async def test_speechkit_gets_the_voice_as_ogg_opus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = web.json_response({"result": " Лифт застрял "})

    text, sent = await _recognize(monkeypatch, CONFIGURED, reply)

    assert text == "Лифт застрял"
    [(request, body)] = sent
    assert body == AUDIO
    assert request.headers["Authorization"] == "Api-Key key"
    assert dict(request.query) == {
        "folderId": "folder",
        "lang": "ru-RU",
        "format": "oggopus",
    }


@pytest.mark.parametrize(
    ("config", "reply", "calls"),
    [
        (
            YandexConfig(api_key=None, folder_id=None),
            web.json_response({"result": "Лифт"}),
            0,
        ),
        (CONFIGURED, web.json_response({"error_code": "BAD_REQUEST"}, status=400), 1),
        (CONFIGURED, web.Response(text="<html>Bad Gateway</html>"), 1),
    ],
)
async def test_speechkit_failure_leaves_the_voice_unrecognized(
    monkeypatch: pytest.MonkeyPatch,
    config: YandexConfig,
    reply: web.StreamResponse,
    calls: int,
) -> None:
    text, sent = await _recognize(monkeypatch, config, reply)

    assert text == ""
    assert len(sent) == calls
