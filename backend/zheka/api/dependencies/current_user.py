import hmac
import urllib.parse
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from maxo.errors import InvalidWebAppInitDataError
from maxo.utils.webapp import (
    WebAppChat,
    WebAppInitData,
    WebAppUser,
    safe_parse_webapp_init_data,
)

from zheka.config import Config
from zheka.core.errors import Unauthorized
from zheka.core.ids import API_CHECKER_MAX_USER_ID

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
        raise Unauthorized("Невалидная initData") from error


CurrentUserDep = Annotated[WebAppInitData, Depends(get_current_user)]


def _signed_init_data(token: str, raw: str) -> WebAppInitData:
    if any("\n" in key + value for key, value in urllib.parse.parse_qsl(raw)):
        raise InvalidWebAppInitDataError("Перевод строки в initData")
    return safe_parse_webapp_init_data(token, raw)
