import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from zheka.api.schemas.base import ApiError, BaseError
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidValue,
    NotEnoughRights,
    Unauthorized,
    ZhekaError,
)

logger = logging.getLogger(__name__)


def error_response(
    request: Request,
    status_code: int,
    title: str,
    detail: str,
) -> Response:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            ApiError(
                status=status_code,
                ok=False,
                trace_id=request.state.trace_id,
                error=BaseError(title=title, detail=detail),
            ),
        ),
    )


def _domain_handler(status_code: int) -> Callable[[Request, Any], Awaitable[Response]]:
    async def handler(request: Request, exc: ZhekaError) -> Response:
        logger.debug("%s", status_code, exc_info=exc)
        return error_response(request, status_code, exc.title, str(exc))

    return handler


async def value_error_handler(request: Request, exc: ValueError) -> Response:
    logger.debug("409_CONFLICT", exc_info=exc)
    return error_response(
        request,
        status.HTTP_409_CONFLICT,
        "ValueError",
        str(exc),
    )


async def validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> Response:
    logger.debug("400_BAD_REQUEST", exc_info=exc)
    detail = "\n\n".join(
        f"Поле: {error['loc']}\nОшибка: {error['type']}: {error['msg']}"
        for error in exc.errors()
    )
    return error_response(
        request,
        status.HTTP_400_BAD_REQUEST,
        "RequestValidationError",
        detail,
    )


async def http_handler(request: Request, exc: StarletteHTTPException) -> Response:
    logger.debug("HTTP_EXCEPTION", exc_info=exc)
    return error_response(
        request,
        exc.status_code,
        "HttpException",
        str(exc.detail or "Что-то пошло не так"),
    )


async def unknown_handler(request: Request, exc: Exception) -> Response:
    logger.error("500_INTERNAL_SERVER_ERROR", exc_info=exc)
    return error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "InternalServerError",
        "Внутренняя ошибка сервера",
    )


exception_handlers: dict[Any, Any] = {
    **{
        error: _domain_handler(code)
        for error, code in (
            (Unauthorized, status.HTTP_401_UNAUTHORIZED),
            (NotEnoughRights, status.HTTP_403_FORBIDDEN),
            (EntityNotFound, status.HTTP_404_NOT_FOUND),
            (InvalidRequest, status.HTTP_400_BAD_REQUEST),
            (InvalidValue, status.HTTP_409_CONFLICT),
        )
    },
    ValueError: value_error_handler,
    RequestValidationError: validation_handler,
    StarletteHTTPException: http_handler,
    Exception: unknown_handler,
}


# один и тот же конверт на всех маршрутах, иначе ApiError не попадает
# в OpenAPI и фронт не может сгенерировать тип ошибки. "default" закрывает
# автоматический 422: валидация отвечает 400 тем же конвертом
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": ApiError[BaseError], "description": description}
    for code, description in (
        (status.HTTP_400_BAD_REQUEST, "Некорректный запрос"),
        (status.HTTP_401_UNAUTHORIZED, "Требуется авторизация"),
        (status.HTTP_403_FORBIDDEN, "Недостаточно прав"),
        (status.HTTP_404_NOT_FOUND, "Сущность не найдена"),
        (status.HTTP_409_CONFLICT, "Конфликт состояния"),
        (status.HTTP_500_INTERNAL_SERVER_ERROR, "Внутренняя ошибка сервера"),
        ("default", "Любая другая ошибка, конверт тот же"),
    )
}
