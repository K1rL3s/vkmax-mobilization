import asyncio
import sys

import granian
from granian.constants import Interfaces

from zheka.config import load_config

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = load_config()
    granian.Granian(
        "zheka.api.asgi:app",
        address=config.api.host,
        port=config.api.port,
        workers=config.api.workers,
        interface=Interfaces.ASGI,
        reload=False,
        log_access=True,
        log_enabled=False,
    ).serve()
