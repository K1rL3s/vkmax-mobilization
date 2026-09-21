import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, Header
from maxo.errors import InvalidWebAppInitDataError
from maxo.utils.webapp import WebAppInitData, safe_parse_webapp_init_data

from zheka.base import ZhekaType
from zheka.config import MaxConfig
from zheka.core.errors import Unauthorized
from zheka.core.ids import MaxUserId

INIT_DATA_TTL = timedelta(days=1)


class CurrentUser(ZhekaType):
    max_user_id: MaxUserId
    init_data: WebAppInitData


def parse_init_data(token: str, raw: str) -> WebAppInitData:
    try:
        init_data = safe_parse_webapp_init_data(token, raw)
    except (InvalidWebAppInitDataError, ValueError):
        init_data = safe_parse_webapp_init_data(token, urllib.parse.unquote(raw))
    signed_at = datetime.fromtimestamp(int(init_data.auth_date or 0), UTC)
    if datetime.now(UTC) - signed_at > INIT_DATA_TTL:
        raise InvalidWebAppInitDataError("initData старше суток")
    return init_data


@inject
async def get_current_user(
    *, config: FromDishka[MaxConfig], raw_init_data: str = Header(alias="WebAppData")
) -> CurrentUser:
    try:
        init_data = parse_init_data(config.token, raw_init_data)
    except (InvalidWebAppInitDataError, ValueError) as error:
        raise Unauthorized("Невалидная или устаревшая initData") from error

    return CurrentUser(max_user_id=MaxUserId(init_data.user.id), init_data=init_data)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
