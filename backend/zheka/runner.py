import asyncio
import contextlib
import logging
import sys
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)


def run(entrypoint: Coroutine[Any, Any, Any]) -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    if __debug__:
        runner = asyncio.run
    else:
        try:
            import uvloop  # noqa: PLC0415

            runner = uvloop.run  # type: ignore[assignment]
        except ImportError:
            runner = asyncio.run

    logger.debug("Выбран runner %s", runner)

    with contextlib.suppress(KeyboardInterrupt):
        runner(entrypoint)
