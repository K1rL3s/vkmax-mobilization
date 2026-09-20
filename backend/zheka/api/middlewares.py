import logging
import time
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from zheka.broker.publisher import TaskPublisher
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


async def transaction_middleware(request: Request, call_next: Call) -> Response:
    # транзакцию закрывает ответ, а не провайдер сессии: обработчики доменных
    # ошибок стоят внутри контейнера dishka, поэтому 404 и 409 приезжают сюда
    # уже ответом, а не исключением, и решить по ним может только тот, кто их
    # видит. Исключение сюда доходит только необработанное - откат и наверх,
    # пятисотку рисует ServerErrorMiddleware
    container = request.state.dishka_container
    session: AsyncSession = await container.get(AsyncSession)
    publisher: TaskPublisher = await container.get(TaskPublisher)
    try:
        response = await call_next(request)
    except Exception:
        await session.rollback()
        raise

    if response.status_code < HTTPStatus.BAD_REQUEST:
        await session.commit()
        # задачи уезжают только теперь: до коммита они рассказали бы о том,
        # чего в базе еще нет, а после отката - о том, чего не будет
        await publisher.flush()
    else:
        await session.rollback()
    return response
