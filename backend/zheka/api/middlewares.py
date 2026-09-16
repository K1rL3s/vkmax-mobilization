import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import Response

from zheka.logger.context import trace_id

logger = logging.getLogger(__name__)

TRACE_HEADER = "X-Trace-Id"

Call = Callable[[Request], Awaitable[Response]]


async def trace_id_middleware(request: Request, call_next: Call) -> Response:
    incoming = request.headers.get(TRACE_HEADER) or str(uuid4())

    request.state.trace_id = incoming
    token = trace_id.set(incoming)
    try:
        response = await call_next(request)
    finally:
        trace_id.reset(token)

    response.headers[TRACE_HEADER] = incoming
    return response


async def request_logging_middleware(request: Request, call_next: Call) -> Response:
    started = time.perf_counter()
    logger.info("Запрос: %s %s", request.method, request.url.path)

    response = await call_next(request)

    elapsed = (time.perf_counter() - started) * 1000
    logger.info(
        "Ответ: %s %s -> %s за %.1f мс",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response
