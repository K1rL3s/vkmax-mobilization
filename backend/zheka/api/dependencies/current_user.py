import hashlib
import hmac
import json
import logging
import urllib.parse
from dataclasses import replace
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from maxo.errors import InvalidWebAppInitDataError
from maxo.utils.webapp import (
    WebAppChat,
    WebAppInitData,
    WebAppUser,
    check_webapp_signature,
    parse_webapp_init_data,
)

from zheka.config import Config
from zheka.core.errors import Unauthorized
from zheka.core.ids import API_CHECKER_MAX_USER_ID

logger = logging.getLogger(__name__)

WITHOUT_IP = frozenset("DEF")
WITHOUT_CHAT = json.dumps({"id": 0, "type": "DIALOG"})

API_CHECKER = WebAppInitData(
    chat=WebAppChat(id=API_CHECKER_MAX_USER_ID, type="DIALOG"),
    user=WebAppUser(id=API_CHECKER_MAX_USER_ID, first_name="Проверяющий API"),
    hash="",
)

test_token_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="ApiTestToken",
    description=(
        "Тестовый токен из API_TEST_TOKEN для автоматической проверки API: "
        "запросы идут от одного синтетического пользователя. Мини-приложение "
        "передает заголовок WebAppData"
    ),
)


def parse_init_data(token: str, raw: str) -> WebAppInitData:
    try:
        return _signed_init_data(token, raw)
    except (InvalidWebAppInitDataError, ValueError):
        return _signed_init_data(token, urllib.parse.unquote(raw))


@inject
async def get_current_user(
    *,
    request: Request,
    config: FromDishka[Config],
    raw_init_data: Annotated[str | None, Header(alias="WebAppData")] = None,
    bearer: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(test_token_scheme),
    ] = None,
) -> WebAppInitData:
    test_token = config.api.test_token
    if (
        bearer is not None
        and test_token
        and hmac.compare_digest(bearer.credentials.encode(), test_token.encode())
    ):
        return API_CHECKER
    if raw_init_data is None:
        raise Unauthorized("Нужна initData в заголовке WebAppData или тестовый токен")
    try:
        return parse_init_data(config.max.token, raw_init_data)
    except (InvalidWebAppInitDataError, ValueError) as error:
        logger.warning(
            "Невалидная initData: %s, User-Agent %s",
            init_data_shape(raw_init_data),
            request.headers.get("user-agent"),
        )
        raise Unauthorized("Невалидная initData") from error


CurrentUserDep = Annotated[WebAppInitData, Depends(get_current_user)]


def _signed_init_data(token: str, raw: str) -> WebAppInitData:
    if any("\n" in key + value for key, value in urllib.parse.parse_qsl(raw)):
        raise InvalidWebAppInitDataError("Перевод строки в initData")
    variant = signature_variant(token, raw)
    if variant is None:
        raise InvalidWebAppInitDataError("Invalid init data signature")
    if "chat" not in dict(urllib.parse.parse_qsl(raw)):
        raw = f"{raw}&{urllib.parse.urlencode({'chat': WITHOUT_CHAT})}"
    init_data = parse_webapp_init_data(raw)
    if variant == "A":
        return init_data
    logger.info("initData подошла по варианту подписи %s", variant)
    return replace(init_data, ip=None) if variant in WITHOUT_IP else init_data


def init_data_shape(raw: str) -> str:
    names = [name for name, _ in urllib.parse.parse_qsl(raw, keep_blank_values=True)]
    keys = [name for name in names if name.isascii() and name.isidentifier()]
    marks = {mark: mark in raw for mark in ("{", "%25", "+", "%7B")}
    return (
        f"ключи {sorted(keys)}, прочих частей {len(names) - len(keys)}, "
        f"hash {'hash' in keys}, длина {len(raw)}, есть {marks}"
    )


def signature_variant(token: str, raw: str) -> str | None:
    if check_webapp_signature(token, raw):
        return "A"
    decoded = dict(urllib.parse.parse_qsl(raw))
    with_blanks = dict(urllib.parse.parse_qsl(raw, keep_blank_values=True))
    raw_pairs = {
        key: value for key, _, value in (part.partition("=") for part in raw.split("&"))
    }
    candidates = [("B", with_blanks), ("C", raw_pairs)]
    if "ip" in with_blanks:
        candidates += [
            ("D", _without_ip(decoded)),
            ("E", _without_ip(with_blanks)),
            ("F", _without_ip(raw_pairs)),
        ]
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    return next(
        (variant for variant, fields in candidates if _signed(secret, fields)),
        None,
    )


def _without_ip(fields: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in fields.items() if key != "ip"}


def _signed(secret: bytes, fields: dict[str, str]) -> bool:
    expected = fields.get("hash")
    if expected is None:
        return False
    check = "\n".join(
        f"{key}={value}" for key, value in sorted(fields.items()) if key != "hash"
    )
    signature = hmac.new(
        secret,
        check.encode(errors="surrogatepass"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(
        signature.encode(),
        expected.encode(errors="surrogatepass"),
    )
